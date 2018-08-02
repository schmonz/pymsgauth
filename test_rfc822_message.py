#!/opt/pkg/bin/python3.7

import unittest

import codecs
import email
import os
import sys


class RFC822Message:
    def __init__(self, buf):
        self.message = email.message_from_file(buf)
        self.headers = self.init_headers()
        self.fp = self.init_fp(buf)

    def init_headers(self):
        headers = []
        for field, value in self.message.items():
            headers.extend(field + ': ' + value + '\n')
        return headers

    def init_fp(self, buf):
        if buf != sys.stdin:
            buf.seek(0)
            while '\n' != buf.readline():
                pass
        return buf

    def getaddr(self, field):
        value = self.message.get(field)
        if value == None:
            name = None
            addr = None
        else:
            name, addr = email.utils.parseaddr(value)
        return name, addr

    def getheader(self, field, default):
        return self.message.get(field, '')

    def getaddrlist(self, field):
        addrlist = []
        values = self.message.get_all(field)
        if values:
            for value in values:
                name_addr = email.utils.parseaddr(value)
                addrlist.append(name_addr)
        return addrlist

    def rewindbody(self):
        self.init_fp(self.fp)


class TestRFC822Message(unittest.TestCase):
    def message3(self, which):
        self.f = open('sample_message_' + which + '.txt', 'r')
        self.message = RFC822Message(self.f)

    def setUp(self):
        self.f = None
        self.message = None

    def tearDown(self):
        if self.f:
            self.f.close()

    def test_headers_preserves_order(self):
        self.message3('in')

        expected_headers_in_order = """From: "Amitai Schleier" <schmonz@schmonz.com>
Cc: archive@schmonz.com (Archive Schmonz)
To: qmail@list.cr.yp.to
Subject: announce: queue-repair-symlink3 patch
Date: Mon, 30 Jul 2018 09:09:23 +0200
X-Mailer: MailMate (1.11.3r5509)
Message-ID: <41B7E795-1B64-4D77-B8B1-6C74A71DF6C7@schmonz.com>
MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8; format=flowed
Content-Transfer-Encoding: 8bit
"""
        actual_headers = self.message.headers

        self.assertIsInstance(actual_headers, list)
        self.assertEqual(expected_headers_in_order, ''.join(self.message.headers))

    def test_readline_fp_reads_line(self):
        self.message3('in')

        line1 = self.message.fp.readline()
        line2 = self.message.fp.readline()
        line3 = self.message.fp.readline()

        self.assertTrue(line1.startswith('This patch '))
        self.assertTrue(line2.startswith('(http://pyropus.ca'))
        self.assertEqual(u"\n", line3)

    def test_rewindbody_on_stdin_does_not_rewind(self):
        sys.stdin = os.fdopen(sys.stdin.fileno(), 'rb', 0)
        sys.stdin = codecs.getreader('utf-8')(sys.stdin)
        message = RFC822Message(sys.stdin)

        message.fp.readline()
        message.fp.readline()
        message.fp.readline()
        message.rewindbody()
        current_line = message.fp.readline()

        self.assertFalse(current_line.startswith('This patch '))

    def test_rewindbody_on_file_rewinds(self):
        self.message3('in')

        self.message.fp.readline()
        self.message.fp.readline()
        self.message.fp.readline()
        self.message.rewindbody()
        current_line = self.message.fp.readline()

        self.assertTrue(current_line.startswith('This patch '))

    def test_getaddr_on_missing_header_gives_none(self):
        self.message3('in')

        blorf_name, blorf_addr = self.message.getaddr('blorf')

        self.assertEqual(None, blorf_name)
        self.assertEqual(None, blorf_addr)

    def test_getaddr_on_non_address_header_still_parses(self):
        self.message3('in')

        mailer_name, mailer_addr = self.message.getaddr('x-mailer')

        self.assertEqual('1.11.3r5509', mailer_name)
        self.assertEqual('MailMate', mailer_addr)

        mimeversion_name, mimeversion_addr = self.message.getaddr('mime-version')

        self.assertEqual('', mimeversion_name)
        self.assertEqual('1.0', mimeversion_addr)

    def test_getaddr_on_sensible_header_gives_values(self):
        self.message3('in')

        from_name, from_addr = self.message.getaddr('from')

        self.assertEqual('Amitai Schleier', from_name)
        self.assertEqual('schmonz@schmonz.com', from_addr)

    def test_getaddr_on_also_sensible_header_gives_values(self):
        self.message3('in')

        from_name, from_addr = self.message.getaddr('cc')

        self.assertEqual('Archive Schmonz', from_name)
        self.assertEqual('archive@schmonz.com', from_addr)

    def test_getheader_on_missing_header_gives_empty(self):
        self.message3('out')
        field = 'X-totally-invented-for-this-test'

        header = self.message.getheader(field, '')

        self.assertEqual(0, len(header))
        self.assertRegex(header, r'^$')

    def test_getheader_on_present_header_gives_value(self):
        self.message3('out')
        field = 'X-pymsgauth-token'

        header = self.message.getheader(field, '')

        self.assertEqual(40, len(header))
        self.assertRegex(header, r'[:xdigit:]+')

    def test_getaddrlist_makes_tuples(self):
        self.message3('in')

        recipients = []
        self.assertEqual(0, len(recipients))

        recipients.extend(self.message.getaddrlist('to'))
        self.assertEqual(1, len(recipients))

        name, addr = recipients[0]
        self.assertEqual('', name)
        self.assertEqual('qmail@list.cr.yp.to', addr)

        recipients.extend(self.message.getaddrlist('blorf'))
        self.assertEqual(1, len(recipients))

        recipients.extend(self.message.getaddrlist('from'))
        self.assertEqual(2, len(recipients))

        name, addr = recipients[1]
        self.assertEqual('Amitai Schleier', name)
        self.assertEqual('schmonz@schmonz.com', addr)

if __name__ == '__main__':
    unittest.main()
