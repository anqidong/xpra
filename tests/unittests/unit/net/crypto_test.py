#!/usr/bin/env python3
# This file is part of Xpra.
# Copyright (C) 2011-2020 Antoine Martin <antoine@xpra.org>
# Copyright (C) 2008, 2009, 2010 Nathaniel Smith <njs@pobox.com>
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

import unittest
from time import monotonic
from xpra.os_util import hexstr
from xpra.util import envbool

from xpra.net.crypto import (
    DEFAULT_SALT, DEFAULT_ITERATIONS, DEFAULT_BLOCKSIZE, DEFAULT_IV,
    validate_backend,
    )

SHOW_PERF = envbool("XPRA_SHOW_PERF", False)


def log(_message):
    #print(message[:256])
    pass


class TestCrypto(unittest.TestCase):

    def setUp(self):
        from xpra.net import pycryptography_backend
        pycryptography_backend.init()
        self.backend = pycryptography_backend

    def do_test_backend(self, message=b"some message1234", encrypt_count=1, decrypt_count=1):
        def mustequ(l):
            if not l:
                return
            v = l[0]
            size = len(l)
            for i in range(size):
                assert l[i]==v

        password = "this is our secret"
        key_salt = DEFAULT_SALT
        iterations = DEFAULT_ITERATIONS
        block_size = DEFAULT_BLOCKSIZE
        #test key stretching:
        args = password, key_salt, block_size, iterations
        secret = self.backend.get_key(*args)
        log("%s%s=%s" % (self.backend.get_key, args, hexstr(secret)))
        assert secret is not None
        #test creation of encryptors and decryptors:
        iv = DEFAULT_IV
        args = secret, iv
        enc = self.backend.get_encryptor(*args)
        log("%s%s=%s" % (self.backend.get_encryptor, args, enc))
        assert enc is not None
        dec = self.backend.get_decryptor(*args)
        log("%s%s=%s" % (self.backend.get_decryptor, args, dec))
        assert dec is not None
        #print("init took %ims", (monotonic()-start)//1000)
        #test encoding of a message:
        encrypted = []
        for i in range(encrypt_count):
            v = enc.encrypt(message)
            #print("%s%s=%s" % (enc.encrypt, (message,), hexstr(v)))
            assert v is not None
            if i==0:
                encrypted.append(v)
        mustequ(encrypted)
        #test decoding of the message:
        decrypted = []
        for i in range(decrypt_count):
            v = dec.decrypt(encrypted[0])
            log("%s%s=%s" % (dec.decrypt, (encrypted[0],), hexstr(v)))
            assert v is not None
            if i==0:
                decrypted.append(v)
        mustequ(decrypted)
        if decrypted:
            mustequ([decrypted[0], message])

    def test_backends(self):
        self.do_test_backend()

    def do_test_perf(self, size=1024*4, enc_iterations=20, dec_iterations=20):
        asize = (size+15)//16
        times = []
        data = b"0123456789ABCDEF"*asize
        start = monotonic()
        self.do_test_backend(data, enc_iterations, dec_iterations)
        end = monotonic()
        elapsed = max(0.0001, end-start)
        speed = (asize*16) * (enc_iterations + dec_iterations) / elapsed
        iter_time = elapsed*1000/(enc_iterations + dec_iterations)
        print("%10iKB: %5.1fms: %16iMB/s" % (asize*16//1024, iter_time, speed//1024//1024))
        times.append(end-start)
        return times

    def test_perf(self):
        if not SHOW_PERF:
            return
        #RANGE = (1, 256, 1024, 1024*1024, 1024*1024*16)
        RANGE = (1024, 1024*1024)
        print("Python Cryptography:")
        print("  Encryption:")
        for i in RANGE:
            self.do_test_perf(i, 10, 0)
        print("  Decryption:")
        for i in RANGE:
            self.do_test_perf(i, 1, 10)
        print("  Overall:")
        for i in RANGE:
            self.do_test_perf(i, 10, 10)

    def test_crypto(self):
        validate_backend(self.backend)


def main():
    unittest.main()

if __name__ == '__main__':
    main()
