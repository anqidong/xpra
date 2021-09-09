# This file is part of Xpra.
# Copyright (C) 2021 Antoine Martin <antoine@xpra.org>
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

import struct
from xpra.net.rfb.rfb_protocol import RFBProtocol
from xpra.net.rfb.rfb_const import RFBEncoding, RFBClientMessage, RFBAuth, CLIENT_INIT
from xpra.os_util import hexstr, bytestostr
from xpra.util import repr_ellipsized
from xpra.log import Logger

log = Logger("network", "protocol", "rfb")


class RFBClientProtocol(RFBProtocol):

    def __init__(self, scheduler, conn, process_packet_cb, next_packet):
        #TODO: start a thread to process this:
        self.next_packet = next_packet
        super().__init__(scheduler, conn, process_packet_cb)

    def source_has_more(self):
        log.warn("source_has_more")

    def handshake_complete(self):
        log.info("RFB connected to %s", self._conn.target)
        self._packet_parser = self._parse_security_handshake
        self.send_protocol_handshake()

    def _parse_security_handshake(self, packet):
        log("parse_security_handshake(%s)", hexstr(packet))
        n = struct.unpack(b"B", packet[:1])[0]
        if n==0:
            self._internal_error(packet, "cannot parse security handshake '%s'" % hexstr(packet))
            return 0
        security_types = struct.unpack(b"B"*n, packet[1:])
        st = []
        for v in security_types:
            try:
                v = RFBAuth(v)
            except ValueError:
                pass
            st.append(v)
        log("parse_security_handshake(%s) security_types=%s", hexstr(packet), st)
        if st and st[0]!=RFBAuth.NONE:
            self._internal_error(packet, "security type %s not supported yet" % (st[0]))
            return 0
        self._packet_parser = self._parse_security_result
        packet = struct.pack(b"B", 0)
        self.send(packet)
        return 1+n

    def _parse_security_result(self, packet):
        if len(packet)<4:
            return 0
        r = struct.unpack(b"I", packet[:4])[0]
        if r!=0:
            self._internal_error(packet, "authentication denied, server returned %i", r)
            return 0
        log("parse_security_result(%s) success", hexstr(packet))
        self._packet_parser = self._parse_client_init
        share = False
        packet = struct.pack(b"B", bool(share))
        self.send(packet)
        return 4

    def _parse_client_init(self, packet):
        log.info("_parse_client_init(%s)", packet)
        ci_size = struct.calcsize(CLIENT_INIT)
        if len(packet)<ci_size:
            return 0
        #the last item in client init is the length of the session name:
        name_size =  struct.unpack(CLIENT_INIT, packet[:ci_size])[-1]
        #do we have enough to parse that too?
        if len(packet)<ci_size+name_size:
            return 0
        #TODO: parse size and create a window
        session_name = bytestostr(packet[ci_size:ci_size+name_size])
        log.info("RFB server session '%s'", session_name)
        self._packet_parser = self._parse_rfb_packet
        self.send_set_encodings()
        return ci_size+name_size

    def send_set_encodings(self):
        packet = struct.pack("!BBHi", RFBClientMessage.SetEncodings, 0, 1, RFBEncoding.RAW)
        self.send(packet)

    def _parse_rfb_packet(self, packet):
        log.info("parse_rfb_packet(%s)", repr_ellipsized(packet))
        header_size = struct.calcsize(b"!BBHHHHHi")
        if len(packet)<=header_size:
            return 0
        if packet[:4]!=struct.pack(b"!BBH", 0, 0, 1):
            self.invalid("unknown packet", packet)
            return 0
        x, y, w, h, encoding = struct.unpack(b"!HHHHi", packet[4:header_size])
        if encoding!=RFBEncoding.RAW:
            self.invalid("invalid encoding: %s" % encoding, packet)
            return
        log.info("screen update: %s", (x, y, w, h))
        if len(packet)<header_size + w*h*4:
            return 0
        return header_size + w*h*4
        #rect = struct.pack(b"!HHHHi", x, y, w, h, encoding)
