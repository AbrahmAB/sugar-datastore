import unittest
from testutils import tmpData

from olpc.datastore import DataStore
from olpc.datastore import model 
import datetime

class Test(unittest.TestCase):
    def test_dateproperty(self):
        n = datetime.datetime.now()
        # we have to kill the microseconds as
        # time.strptime which we must use in 2.4 doesn't parse it
        n = n.replace(microsecond=0)
        p = model.DateProperty('ctime', n)
        assert p.key == "ctime"
        assert p.value.isoformat() == n.isoformat()

    def test_binaryproperty(self):
        ds = DataStore('/tmp/test_ds', 'sqlite://')

        data = open('test.jpg', 'r').read()
        # binary data with \0's in it can cause dbus errors here
        uid = ds.create(dict(title="Document 1", thumbnail=data),
                        tmpData("with image\0\0 prop"))
        c = ds.get(uid)
        assert c.get_property('thumbnail') == data
        ds.stop()
        
        
def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(Test))
    return suite

if __name__ == "__main__":
    unittest.main()
                    
