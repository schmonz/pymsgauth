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

    def test_headers_preserves_order(self):
        message = self.message('in')

        expected_headers_in_order = """From: "Amitai Schleier" <schmonz@schmonz.com>
To: qmail@list.cr.yp.to
Subject: announce: queue-repair-symlink3 patch
Date: Mon, 30 Jul 2018 09:09:23 +0200
X-Mailer: MailMate (1.11.3r5509)
Message-ID: <41B7E795-1B64-4D77-B8B1-6C74A71DF6C7@schmonz.com>
MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8; format=flowed
Content-Transfer-Encoding: 8bit
"""
        actual_headers = message.headers

        self.assertIsInstance(actual_headers, list)
        self.assertEqual(expected_headers_in_order, ''.join(message.headers))

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

    def test_getaddrlist_makes_tuples(self):
        message = self.message('in')

        recipients = []
        self.assertEqual(0, len(recipients))

        recipients.extend(message.getaddrlist('to'))
        self.assertEqual(1, len(recipients))

        name, addr = recipients[0]
        self.assertEqual('', name)
        self.assertEqual('qmail@list.cr.yp.to', addr)

        recipients.extend(message.getaddrlist('cc'))
        self.assertEqual(1, len(recipients))

        recipients.extend(message.getaddrlist('from'))
        self.assertEqual(2, len(recipients))

        name, addr = recipients[1]
        self.assertEqual('Amitai Schleier', name)
        self.assertEqual('schmonz@schmonz.com', addr)

if __name__ == '__main__':
    unittest.main()
