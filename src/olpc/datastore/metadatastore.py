import os

from olpc.datastore import layoutmanager
from olpc.datastore import metadatareader

MAX_SIZE = 256

class MetadataStore(object):
    def store(self, uid, metadata):
        dir_path = layoutmanager.get_instance().get_entry_path(uid)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        metadata_path = os.path.join(dir_path, 'metadata')
        if not os.path.exists(metadata_path):
            os.makedirs(metadata_path)
        else:
            for key in os.listdir(metadata_path):
                os.remove(os.path.join(metadata_path, key))

        metadata['uid'] = uid
        for key, value in metadata.items():
            open(os.path.join(metadata_path, key), 'w').write(str(value))

    def retrieve(self, uid, properties=None):
        dir_path = layoutmanager.get_instance().get_entry_path(uid)
        return metadatareader.retrieve(dir_path, properties)

    def delete(self, uid):
        dir_path = layoutmanager.get_instance().get_entry_path(uid)
        metadata_path = os.path.join(dir_path, 'metadata')
        for key in os.listdir(metadata_path):
            os.remove(os.path.join(metadata_path, key))
        os.rmdir(metadata_path)

    def get_property(self, uid, key):
        dir_path = layoutmanager.get_instance().get_entry_path(uid)
        metadata_path = os.path.join(dir_path, 'metadata')
        property_path = os.path.join(metadata_path, key)
        if os.path.exists(property_path):
            return open(property_path, 'r').read()
        else:
            return None

    def set_property(self, uid, key, value):
        dir_path = layoutmanager.get_instance().get_entry_path(uid)
        metadata_path = os.path.join(dir_path, 'metadata')
        property_path = os.path.join(metadata_path, key)
        open(property_path, 'w').write(value)

