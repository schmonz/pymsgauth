#!/opt/pkg/bin/python2.7

import unittest

import codecs
import io
import rfc822
import sys

sys.stdin = codecs.getreader('utf-8')(sys.stdin)
buf = io.StringIO (u'' + sys.stdin.read())

class TestRFC822Message(unittest.TestCase):
    def test_can_readline_fp(self):
        message = rfc822.Message(buf)

        self.assertTrue(message.fp.readline().startswith('This patch '))
        self.assertTrue(message.fp.readline().startswith('(http://pyropus.ca'))
        self.assertEqual(u"\n", message.fp.readline())

    def test_cannot_rewindbody_stdin(self):
        message = rfc822.Message(buf)
        message.fp.readline()
        message.fp.readline()
        message.fp.readline()
        message.rewindbody()

        self.assertFalse(message.fp.readline().startswith('This patch '))

    def test_can_rewindbody_file(self):
        f = open('sample_message.txt', 'r')
        message = rfc822.Message(f)

        message.fp.readline()
        message.fp.readline()
        message.fp.readline()
        message.rewindbody()

        self.assertTrue(message.fp.readline().startswith('This patch '))

if __name__ == '__main__':
    unittest.main()