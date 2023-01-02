from django.test import SimpleTestCase, TestCase

import requests

from utils.renderers import BaseXLSXRenderer
from utils.storages import TempUserFileDownloadStorage, write_file_for_download


class TemporaryUserCreatedFileStorageTestCase(SimpleTestCase):

    def setUp(self):
        self.storage = TempUserFileDownloadStorage()

    def test_write_and_delete(self):
        with self.storage.open('test.csv', 'w') as file:
            file.write('test')
        self.assertTrue(self.storage.exists('test.csv'))
        self.storage.delete('test.csv')
        self.assertFalse(self.storage.exists('test.csv'))


class WriteFileForDownloadTestCase(TestCase):

    def setUp(self):
        self.storage = TempUserFileDownloadStorage()
        if self.storage.exists('test.xlsx'):
            self.storage.delete('test.xlsx')

    def test_returns_valid_signed_download_url(self):
        self.assertFalse(self.storage.exists('test.xlsx'))
        url = write_file_for_download('test.xlsx', {}, BaseXLSXRenderer)
        self.assertTrue(self.storage.exists('test.xlsx'))
        response = requests.get(url)
        self.assertEqual(200, response.status_code)
        self.storage.delete('test.xlsx')
        self.assertFalse(self.storage.exists('test.xlsx'))
