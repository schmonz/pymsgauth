#!/opt/pkg/bin/python2.7

import unittest

import codecs
import io
import rfc822
import sys

sys.stdin = codecs.getreader('utf-8')(sys.stdin)
buf = io.StringIO (u'' + sys.stdin.read())

class TestRFC822Message(unittest.TestCase):
    def message(self, which):
        f = open('sample_message_' + which + '.txt', 'r')
        return rfc822.Message(f)

    def test_readline_fp_reads_line(self):
        message = rfc822.Message(buf)

        line1 = message.fp.readline()
        line2 = message.fp.readline()
        line3 = message.fp.readline()

        self.assertTrue(line1.startswith('This patch '))
        self.assertTrue(line2.startswith('(http://pyropus.ca'))
        self.assertEqual(u"\n", line3)

    def test_rewindbody_on_stdin_does_not_rewind(self):
        message = rfc822.Message(buf)

        message.fp.readline()
        message.fp.readline()
        message.fp.readline()
        message.rewindbody()
        current_line = message.fp.readline()

        self.assertFalse(current_line.startswith('This patch '))

    def test_rewindbody_on_file_rewinds(self):
        message = self.message('in')

        message.fp.readline()
        message.fp.readline()
        message.fp.readline()
        message.rewindbody()
        current_line = message.fp.readline()

        self.assertTrue(current_line.startswith('This patch '))

    def test_getaddr_on_missing_header_gives_none(self):
        message = self.message('in')

        blorf_name, blorf_addr = message.getaddr('blorf')

        self.assertEquals(None, blorf_name)
        self.assertEquals(None, blorf_addr)

    def test_getaddr_on_non_address_header_still_parses(self):
        message = self.message('in')

        mailer_name, mailer_addr = message.getaddr('x-mailer')

        self.assertEquals('1.11.3r5509', mailer_name)
        self.assertEquals('MailMate', mailer_addr)

        mimeversion_name, mimeversion_addr = message.getaddr('mime-version')

        self.assertEquals('', mimeversion_name)
        self.assertEquals('1.0', mimeversion_addr)

    def test_getaddr_on_sensible_header_gives_values(self):
        message = self.message('in')

        from_name, from_addr = message.getaddr('from')

        self.assertEquals('Amitai Schleier', from_name)
        self.assertEquals('schmonz@schmonz.com', from_addr)

    def test_getheader_on_missing_header_gives_empty(self):
        message = self.message('out')
        field = 'X-totally-invented-for-this-test'

        header = message.getheader(field, '')

        self.assertEquals(0, len(header))
        self.assertRegexpMatches(header, r'^$')

    def test_getheader_on_present_header_gives_value(self):
        message = self.message('out')
        field = 'X-pymsgauth-token'

        header = message.getheader(field, '')

        self.assertEquals(40, len(header))
        self.assertRegexpMatches(header, r'[:xdigit:]+')

if __name__ == '__main__':
    unittest.main()
