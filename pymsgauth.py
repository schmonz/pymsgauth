#!/usr/bin/python
'''pymsgauth.py - A toolkit for automatically dealing with qsecretary
confirmation notices.
Copyright (C) 2001 Charles Cazabon <software @ discworld.dyndns.org>

This program is free software; you can redistribute it and/or
modify it under the terms of version 2 of the GNU General Public License
as published by the Free Software Foundation.  A copy of this license should
be included in the file COPYING.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.

'''

__version__ = '2.1.0-filter3-20180724'
__author__ = 'Charles Cazabon <software @ discworld.dyndns.org>'


#
# Imports
#

import sys
import os
import string
import email
import io
import time
import types
import ConfParser

if sys.version_info[0] < 3:
    import codecs
    sys.stdin = codecs.getreader('utf-8')(sys.stdin)

#
# Configuration constants
#

# Names for output logging levels
loglevels = {
    'TRACE' : 1,
    'DEBUG' : 2,
    'INFO' : 3,
    'WARN' : 4,
    'ERROR' : 5,
    'FATAL' : 6,
}
(TRACE, DEBUG, INFO, WARN, ERROR, FATAL) = list(range(1, 7))

# Build-in default values
defaults = {
    # In your pymsgauthrc file, set this to the envelope sender address to use
    # when replying to qsecretary notices.
    #'confirmation_address' : 'my_email_address@example.org',

    # In your pymsgauthrc file, set this to a string containing some
    # entropy, to make forging authentications tougher.
    'secret' : '',

    # What is the "real" mail delivery program?  Any arguments passed to the
    # pymsgauth_mail wrapper will be appended to this.  The default should work
    # well.
    'mail_prog' : ['/var/qmail/bin/qmail-inject', '-A'],

    # Anything to add to the mail program commandline?
    'extra_mail_args' : [],

    # What domains to return qsecretary confirmations to
    'confirm_domain' : ['list.cr.yp.to'],

    # Messages to which envelope recipients get an authentication token appended
    'token_recipient' : [
        'qmail@list.cr.yp.to',
        'log@list.cr.yp.to',
        'dns@list.cr.yp.to'
        'ezmlm@list.cr.yp.to',
    ],

    # Default lifetime for authentication tokens, in seconds (3 days)
    # Files in the configuration/data directory beginning with a dot
    # older than this will be deleted.
    'token_lifetime' : 3 * 86400,

    # Name of header field to add/check
    'auth_field' : 'X-pymsgauth-token',

    # Default logging level.  Use INFO for a little more verbosity.
    'log_level' : WARN,

    # Default; log to stdout
    'log_stderr' : 1,

    # Log to file?  Will be expanded for leading user (i.e. '~/logfile')
    'log_file' : None,

    # Default configuration/data directory; override this with the
    # PYMSGAUTH_DIR environment variable
    'pymsgauth_dir' : os.path.expanduser ('~/.pymsgauth'),

    # Configuration file name; will be looked for in the directory specifed
    # above.
    'pymsgauthrc_filename' : 'pymsgauthrc',
}

# Configuration data held here.
config = {}

# Components of stack trace (indices to tuple)
FILENAME, LINENO, FUNCNAME = 0, 1, 2        #SOURCELINE = 3 ; not used

# Open logging file
logfd = None

#############################
class pymsgauthError (Exception):
    pass

#############################
class DeliveryError (pymsgauthError):
    pass

#############################
class ConfigurationError (pymsgauthError):
    pass

#############################
class RFC822Message:
    def __init__(self, buf, seekable=1):
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
            while 1:
                line = buf.readline()
                if line == '\n' or line == '':
                    break
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

#######################################
def log (level=INFO, msg=''):
    global logfd
    if level < config['log_level']:
        return
    if level == TRACE:
        import traceback
        trace = traceback.extract_stack ()[-2]
        s = '%s() [%s:%i] %s\n' % (trace[FUNCNAME],
            os.path.split (trace[FILENAME])[-1],
            trace[LINENO], msg)
    else:
        s = msg + '\n'
    if config['log_stderr']:
        sys.stderr.write (s)
        sys.stderr.flush ()
    if config['log_file']:
        if not logfd:
            try:
                logfd = open (os.path.expanduser (config['log_file']), 'a')
            except IOError as txt:
                raise ConfigurationError('failed to open log file %s (%s)' \
                    % (config['log_file'], txt))
        t = time.localtime (time.time ())
        logfd.write ('%s %s' % (time.strftime ('%d %b %Y %H:%M:%S', t), s))
        logfd.flush ()

#############################
def log_exception ():
    import traceback
    exc_type, value, tb = sys.exc_info()
    lines = ['Traceback: ']
    lines.extend (traceback.format_tb (tb))
    for line in lines:
        log (FATAL, line[:-1])

#############################
def read_config ():
    config.update (defaults)
    config['pymsgauth_dir'] = os.environ.get ('PYMSGAUTH_DIR',
        defaults['pymsgauth_dir'])
    config_file = os.path.join (config['pymsgauth_dir'],
        defaults['pymsgauthrc_filename'])
    log (TRACE, 'config_file == %s' % config_file)
    conf = ConfParser.ConfParser ()
    log (TRACE)
    try:
        conf.read (config_file)
        log (TRACE)
        for option in conf.options ('default'):
            value = conf.get ('default', option)
            if option == 'log_level':
                try:
                    value = loglevels[value]
                except KeyError:
                    raise ConfigurationError('"%s" not a valid logging level' % value)
            config[option] = value
            if option == 'secret':
                log (TRACE, 'option secret == %s...' % value[:20])
            else:
                log (TRACE, 'option %s == %s...' % (option, config[option]))
    except (ConfigurationError, ConfParser.ConfParserException) as txt:
        if not os.environ.get ('PYMSGAUTH_TOLERATE_UNCONFIGURED'):
            log (FATAL, 'Fatal:  exception reading %s (%s)' % (config_file, txt))
            raise
    if type (config['token_recipient']) != list:
        config['token_recipient'] = [config['token_recipient']]
    log (TRACE)

#############################
def extract_original_message (msg):
    msg.rewindbody ()
    lines = []
    while 1:
        lines.append (msg.fp.readline())
        if lines[-1] == '':
            del lines[-1]
            break

    # Strip qsecretary text
    found_separator = 0
    while lines and not found_separator:
        if lines[0] == '--- Below this line is the top of your message.\n':
            found_separator = 1
        del lines[0]

    # Strip blank line(s)
    while lines and string.strip (lines[0]) == '':
        del lines[0]

    buf = io.StringIO (''.join (lines))
    buf.seek (0)
    orig_msg = RFC822Message (buf)
    return orig_msg

#############################
def gen_token (msg):
    import hashlib
    lines = []
    contents = '%s,%s,%s,%s' % (os.getpid(), time.time(), ''.join (msg.headers), config['secret'])
    token = hashlib.sha1(contents.encode('utf-8')).hexdigest()
    # Record token
    p = os.path.join (config['pymsgauth_dir'], '.%s' % token)
    try:
        open (p, 'wb')
        log (TRACE, 'Recorded token %s.' % p)
    except IOError as txt:
        log (FATAL, 'Fatal:  exception creating %s (%s)' % (p, txt))
        raise
    return token

#############################
def check_token (msg, token):
    # Find existing token
    p = os.path.join (config['pymsgauth_dir'], '.%s' % token)
    if not os.path.exists (p):
        return 0
    if os.path.islink (p) or not os.path.isfile (p):
        log (WARN, 'Warning:  %s is not a regular file, skipping...' % p)
        return 0
    try:
        log (INFO, 'Matched token %s, removing.' % token)
        os.unlink (p)
        log (TRACE, 'Removed token %s.' % token)
    except OSError as txt:
        log (FATAL, 'Fatal:  error handling token %s (%s)' % (token, txt))
        log_exception ()
        # Exit 0 so qmail delivers the qsecretary notice to user
        sys.exit (0)
    return 1

#############################
def send_mail (msgbuf, mailcmd):
    import subprocess
    log (TRACE, 'Mail command is "%s".' % mailcmd)
    cmd = subprocess.Popen (mailcmd, shell=True, bufsize=-1, universal_newlines=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
    cmdout, cmdin, cmderr = cmd.stdout, cmd.stdin, cmd.stderr

    cmdin.write (msgbuf)
    cmdin.flush ()
    cmdin.close ()
    log (TRACE)

    err = cmderr.read ().strip ()
    cmderr.close ()
    out = cmdout.read ().strip ()
    cmdout.close ()

    r = cmd.wait ()
    log (TRACE, 'r == %s' % r)

    exitcode = 0
    try:
        if r:
            if os.WIFEXITED (r):
                exitcode = os.WEXITSTATUS (r)
                if os.WIFSIGNALED (r):
                    exitsignal = 'signal %s' % os.WTERMSIG (r)
                else:
                    exitsignal = 'no signal'
                if err:
                    errtext = ', err: "%s"' % err
                else:
                    errtext = ''
                raise DeliveryError('mail command %s exited %s, %s%s' \
                    % (mailcmd, exitcode, exitsignal, errtext))
            else:
                exitcode = 127
                raise DeliveryError('mail command %s did not exit (rc == %s)' \
                    % (mailcmd, r))

        if err:
            raise DeliveryError('mail command %s error: "%s"' % (mailcmd, err))
            exitcode = 1

    except DeliveryError as txt:
        log (FATAL, 'Fatal:  failed sending mail (%s)' % txt)
        log_exception ()
        sys.exit (exitcode or 1)

    if out:
        log (WARN, 'Warning:  command "%s" said "%s"' % (mailcmd, out))

    log (TRACE, 'Sent mail.')

#############################
def clean_old_tokens ():
    try:
        import stat
        read_config ()
        log (TRACE)
        oldest = int (time.time()) - config['token_lifetime']
        # Find existing token
        files = os.listdir (config['pymsgauth_dir'])
        for filename in files:
            if filename[0] != '.':
                # Not a token file, skip
                log (TRACE, 'Ignoring file %s.' % filename)
                continue
            p = os.path.join (config['pymsgauth_dir'], filename)
            if os.path.islink (p) or not os.path.isfile (p):
                log (WARN, 'Warning:  %s is not a regular file, skipping...' % p)
                continue
            try:
                s = os.lstat (p)
                if s[stat.ST_CTIME] < oldest:
                    log (INFO, 'Removing old token %s.' % filename)
                    os.unlink (p)
            except OSError as txt:
                log (ERROR, 'Error:  error handling token %s (%s)'
                    % (filename, txt))
                raise

    except Exception as txt:
        log (FATAL, 'Fatal:  caught exception (%s)' % txt)
        log_exception ()
        sys.exit (1)

#############################
def sendmail_wrapper (args):
    try:
        read_config ()
        log (TRACE)
        #mailcmd = (os.environ.get ('MAIL_PROG', config['mail_prog'])
        #    + ' '
        #    + config['extra_mail_args']
        #    + ' '
        #    + string.join (args))
        mailcmd = config['mail_prog'][:]
        if config['extra_mail_args']:
            mailcmd += config['extra_mail_args']
        mailcmd += args
        log (TRACE, 'mailcmd == %s' % mailcmd)
        buf = io.StringIO (u'' + sys.stdin.read())
        new_buf = tokenize_message_if_needed (buf, args)

        send_mail (new_buf, mailcmd)
        if (new_buf != buf.getvalue ()):
            log (TRACE, 'Sent tokenized mail.')
        else:
            log (TRACE, 'Passed mail through unchanged.')

    except Exception as txt:
        log (FATAL, 'Fatal:  caught exception (%s)' % txt)
        log_exception ()
        sys.exit (1)

#############################
def should_tokenize_message (msg, *args):
    try:
        sign_message = 0

        for arg in args:
            if arg in config['token_recipient']:
                sign_message = 1
                break
        if not sign_message:
            recips = []
            for field in ('to', 'cc', 'bcc', 'resent-to', 'resent-cc', 'resent-bcc'):
                recips.extend (msg.getaddrlist (field))
            recips = [name_addr[1] for name_addr in recips]
            for recip in recips:
                if recip in config['token_recipient']:
                    sign_message = 1
                    break

        return sign_message

    except Exception as txt:
        log (FATAL, 'Fatal:  caught exception (%s)' % txt)
        log_exception ()
        sys.exit (1)

#############################
def tokenize_message_if_needed (buf, *args):
    try:
        read_config ()
        log (TRACE)
        msg = RFC822Message (buf, seekable=1)

        if should_tokenize_message (msg, args):
            token = gen_token (msg)
            log (INFO, 'Generated token %s.' % token)
            return '%s: %s\n' % (config['auth_field'], token) + buf.getvalue ()
        else:
            return buf.getvalue ()

    except Exception as txt:
        log (FATAL, 'Fatal:  caught exception (%s)' % txt)
        log_exception ()
        sys.exit (1)

#############################
def process_qsecretary_message ():
    try:
        read_config ()
        log (TRACE)
        buf = io.StringIO (u'' + sys.stdin.read())
        msg = RFC822Message (buf, seekable=1)
        from_name, from_addr = msg.getaddr ('from')
        if from_name != 'The qsecretary program':
            # Not a confirmation message, just quit
            log (TRACE, 'not a confirmation notice (from "%s" <%s>)'
                % (from_name or 'Unknown', from_addr or '<Unknown>'))
            sys.exit (0)

        # Verify the message came from a domain we recognize
        confirm = 0
        domain = string.split (from_addr, '@')[-1]
        cdomains = config['confirm_domain']
        if type (cdomains) != list:  cdomains = [cdomains]
        for cd in cdomains:
            if cd == domain:  confirm = 1
        if not confirm:
            # Didn't come from a site you wish to confirm
            log (INFO, 'Ignored qsecretary notice (incorrect domain), from "%s"'
                % from_addr)
            sys.exit (0)

        # check message here
        orig_msg = extract_original_message (msg)
        orig_token = string.strip (orig_msg.getheader (config['auth_field'], ''))
        if orig_token:
            log (TRACE, 'Received qsecretary notice with token %s.'
                % orig_token)
        else:
            log (WARN, 'Warning:  failed to find token in message from %s.'
                % from_addr)

        if check_token (orig_msg, orig_token):
            try:
                try:
                    source_addr = config['confirmation_address']
                except:
                    raise ConfigurationError('no confirmation_address configured')
                # Confirm this confirmation notice
                #confirm_cmd = config['mail_prog'] \
                #    + ' ' + '-f "%s" "%s"' % (source_addr, from_addr)
                confirm_cmd = config['mail_prog'][:]
                confirm_cmd += ['-f', source_addr, from_addr]
                send_mail ('To: %s\n' % from_addr, confirm_cmd)
                # Drop confirmation notice after replying
                log (INFO, 'Authenticated qsecretary notice, from "%s", token "%s"'
                    % (from_addr, orig_token))
                sys.exit (99)
            except ConfigurationError as txt:
                log (ERROR, 'Error:  failed sending confirmation notice (%s)'
                    % txt)
        else:
            log (ERROR, 'Error:  did not find matching token file (%s)'
                % orig_token)

    except Exception as txt:
        log (FATAL, 'Fatal:  caught exception (%s)' % txt)
        log_exception ()

    # Either the message isn't a qsecretary notice from our message, or
    # it did not match a recorded token, or we errored.
    # Exit 0 to allow it to be delivered to user.
    sys.exit (0)

