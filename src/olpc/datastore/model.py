""" 
olpc.datastore.model
~~~~~~~~~~~~~~~~~~~~
The datamodel for the metadata

""" 

__author__ = 'Benjamin Saller <bcsaller@objectrealms.net>'
__docformat__ = 'restructuredtext'
__copyright__ = 'Copyright ObjectRealms, LLC, 2007'
__license__  = 'The GNU Public License V2+'

from sqlalchemy import Table, Column, UniqueConstraint
from sqlalchemy import String, Integer, Unicode
from sqlalchemy import ForeignKey, Sequence, Index
from sqlalchemy import mapper, relation
from sqlalchemy import create_session
from sqlalchemy import MapperExtension, EXT_PASS, clear_mappers

import datetime
import mimetypes
import os
import time

# XXX: Open issues
# list properties - Contributors (a, b, c)
#                   difficult to index now
# content state   - searches don't include content deletion flag
#                 - not recording if content is on other storage yet


# we have a global thread local session factory
context = {}
propertyTypes = {}
_marker = object()

def get_session(backingstore):
    return context[backingstore]

def registerPropertyType(kind, class_): propertyTypes[kind] = class_
def propertyByKind(kind): return propertyTypes[kind]


class Content(object):
    def __repr__(self):
        return "<Content id:%s>" % (self.id, )

    def get_property(self, key, default=_marker):
        # mapped to property keys
        session = get_session(self.backingstore)
        query = session.query(Property)
        p = query.get_by(content_id=self.id, key=key)
        if not p:
            if default is _marker: raise AttributeError(key)
            return default
        return p.value

    def get_properties(self, **kwargs):
        session = get_session(self.backingstore)
        query = session.query(Property)
        return query.select_by(content_id=self.id, **kwargs)


    # Backingstore dependent bindings 
    def get_file(self):
        if not hasattr(self, "_file") or self._file.closed is True:
            self.backingstore.get(self.id)
        return self._file
    
    def set_file(self, fileobj):
        self._file = fileobj
    file = property(get_file, set_file)

    @property
    def filename(self): return self.file.name

    def suggestName(self):
        # we look for certain known property names
        # - filename
        # - ext
        # and create a base file name that will be used for the
        # checkout name
        filename = self.get_property('filename', None)
        ext = self.get_property('ext', '')

        if filename:
            # some backingstores keep the full relative path
            filename = os.path.split(filename)[1]
            f, e = os.path.splitext(filename)
            if e: return filename, None
            if ext: return "%s.%s" % (filename, ext), None
        elif ext:
            return None, ext
        else:
            # try to get an extension from the mimetype if available
            mt = self.get_property('mime_type', None)
            if mt:
                ext = mimetypes.guess_extension(mt)
                if ext: return None, ext
        return None, None

    def get_data(self):
        f = self.file
        t = f.tell()
        data = f.read()
        f.seek(t)
        return data
    
    def set_data(self, filelike):
        self.backingstore.set(self.id, filelike)

    data = property(get_data, set_data)
    

class BackingStoreContentMapping(MapperExtension):
    """This mapper extension populates Content objects with the
    binding to the backing store the files are kept on, this allow the
    file-like methods to work as expected on content
    """
    def __init__(self, backingstore):
        MapperExtension.__init__(self)
        self.backingstore = backingstore

    def populate_instance(self, mapper, selectcontext, row, instance, identitykey, isnew):
        """called right before the mapper, after creating an instance
        from a row, passes the row to its MapperProperty objects which
        are responsible for populating the object's attributes. If
        this method returns EXT_PASS, it is assumed that the mapper
        should do the appending, else if this method returns any other
        value or None, it is assumed that the append was handled by
        this method.  
        
        """
        instance.backingstore = self.backingstore
        # allow normal population to happen 
        return EXT_PASS

            
class Property(object):
    """A typed key value pair associated with a content object.
    This is the objects metadata. The value side of the kv pair is
    typically encoded as a UTF-8 String. There are however cases where
    richer metadata is required by the application using the
    datastore.
    In these cases the type field is overridden to encode a reference
    to another object that must be used to satisfy this value. An
    example of this would be storing a PNG thumbnail as the a
    value. In a case such as that the value should be set to a path or
    key used to find the image on stable storage or in a database and
    the type field will be used to demarshall it through this object.
    """
    def __init__(self, key, value, type='string'):
        self.key = key
        self.value = value
        self.type = type

    def __repr__(self):
        return "<%s %s:%r>" % (self.__class__.__name__,
                                     self.key, self.value)
    def marshall(self):
        """Return the value marshalled as a string"""
        return str(self.value)

class TextProperty(Property):
    """A text property is one that will also get full automatic text
    indexing when available. This is used for fields like title where
    searching in the text is more important than doing a direct match
    """
    def __init__(self, key, value, type='text'):
        Property.__init__(self, key, value, type)
    
class DateProperty(Property):
    format = "%Y-%m-%dT%H:%M:%S"

    def __init__(self, key, value, type="date"):
        self._value = None
        Property.__init__(self, key, value, type)

    def get_value(self):
        # parse the value back into a datetime
        # XXX: strptime on datetime is a 2.5 thing :(
        # XXX: we lose timezone in this conversion currently
        if not self._value: return None
        ti = time.strptime(self._value, self.format)
        dt = datetime.datetime(*(ti[:-2]))
        dt = dt.replace(microsecond=0)
        return dt

    def set_value(self, value):
        if isinstance(value, basestring):
            # XXX: there  is an issue with microseconds not getting parsed
            ti = time.strptime(value, self.format)
            value = datetime.datetime(*(ti[:-2]))
        value = value.replace(microsecond=0)
            
        self._value = value.isoformat()

    value = property(get_value, set_value)

    def marshall(self): return self.value.isoformat()
    
    
class NumberProperty(Property):
    def __init__(self, key, value, type="number"):
        Property.__init__(self, key, value, type)

    def get_value(self): return float(self._value)
    def set_value(self, value): self._value = value
    value = property(get_value, set_value)
    

class BinaryProperty(Property):
    # base64 encode binary data 
    def __init__(self, key, value, type="binary"):
        Property.__init__(self, key, value, type)

    def get_value(self): return self._value.decode('base64')
    def set_value(self, value): self._value = value.encode('base64')
    value = property(get_value, set_value)


class Model(object):
    """ Manages the global state of the metadata model index. This is
    intended to only be consumed by an olpc.datastore.query.QueryManager
    instance for the management of its metadata.

    >>> m = Model()
    >>> m.prepare(querymanager)

    >>> m.content
    ... # Content Table

    >>> m['content']
    ... # content Mapper

    For details see the sqlalchemy documentation
    
    """
    
    def __init__(self):
        self.tables = {}
        self.mappers = {}
    
    def __getattr__(self, key): return self.tables[key]
    def __getitem__(self, key): return self.mappers[key]



    def prepare(self, querymanager):
        self.querymanager = querymanager

        # a single session manages the exclusive access we keep to the
        # db.
        global context
        self.session = create_session(bind_to=self.querymanager.db)
        context[self.querymanager.backingstore] = self.session
        
        # content object
        content = Table('content',
                        self.querymanager.metadata,
                        Column('id', String, primary_key=True, nullable=False),
                        Column('activity_id', Integer),
                        Column('checksum', String,),
                        UniqueConstraint('id', name='content_key')
                        )
        Index('content_activity_id_idx', content.c.activity_id)
        
        # the properties of content objects
        properties = Table('properties',
                           self.querymanager.metadata,
                           Column('id', Integer, Sequence('property_id_seq'), primary_key=True),
                           Column('content_id', Integer, ForeignKey('content.id')),
                           Column('key', Unicode,  ),
                           Column('value', Unicode, ),
                           Column('type', Unicode, ),
                           # unique key to content mapping
                           UniqueConstraint('content_id', 'key',
                                            name='property_content_key')
                           )
                           
        Index('property_key_idx', properties.c.key)
        Index('property_type_idx', properties.c.type)

        # storage
        storage = Table('storage',
                        self.querymanager.metadata,
                        Column('id', String, primary_key=True),
                        Column('description', String, ),
                        Column('uri', String, )
                        )

        # storage -> * content
        # XXX: this could be a purely runtime in-memory construct
        # removing the storage table as well. Would depend in part on
        # the frequency of the garbage collection runs and the
        # frequency of connection to stable storage
        storage_content = Table('storage_content',
                                self.querymanager.metadata,
                                Column('storage_id', Integer, ForeignKey('storage.id')),
                                Column('content_id', Integer, ForeignKey('content.id')),
                                )
        Index('idx_storage_content_content_id', storage_content.c.content_id)
        
        # Object Mapping
        # the query manager provides a mapping extension for
        # Content <-> BackingStore binding

        # XXX gross and not what we want, we can only define mappers
        # once but we may have more than one datastore.
        # this can impact all sqla in the runtime though
        clear_mappers()

        
        content_mapper = mapper(Content, content,
                                extension=self.querymanager.content_ext,
                                properties = {
                                            'properties' : relation(Property,
                                                                    cascade="all,delete-orphan",
                                                                    backref='content',
                                                                    lazy=True),
                                            },

                                )
        
        # retain reference to these tables to use for queries
        self.tables['content'] = content
        self.tables['properties'] = properties
        self.tables['storage'] = storage
        self.tables['storage_content'] = storage_content

        # and the mappers (though most likely not needed)
        property_mapper = mapper(Property, properties, polymorphic_on=properties.c.type)
        self.mappers['properties'] = property_mapper
        self.mappers['content'] = content_mapper

        # default Property types are mapped to classes here        
        self.addPropertyType(DateProperty, 'date')
        self.addPropertyType(NumberProperty, 'number')
        self.addPropertyType(TextProperty, 'text')
        self.addPropertyType(BinaryProperty, 'binary')
        
        
        

    def addPropertyType(self, PropertyClass, typename,
                        map_value=True, **kwargs):
        """Register a new type of Property. PropertyClass should be a
        subclass of Property, typename is the textual
        name of the new Property type.

        The flag map_value indicates if Property.value should
        automatically be diverted to _value so that you can more
        easily manage the interfaces 'value' as a Python property
        (descriptor)

        Keyword args will be passed to the properties dictionary of
        the sqlalchemy mapper call. See sqlalchemy docs for additional
        details.
        """
        properties = {}
        properties.update(kwargs)
        if map_value is True:
            properties['_value'] = self.properties.c.value
            
        mapper(PropertyClass,
               inherits=self.mappers['properties'],
               polymorphic_identity=typename,
               properties=properties
               )

        registerPropertyType(typename, PropertyClass)

