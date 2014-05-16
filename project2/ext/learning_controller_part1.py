# Copyright 2012 James McCauley
#
# This file is part of POX.
#
# POX is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# POX is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with POX.    If not, see <http://www.gnu.org/licenses/>.


from pox.core import core
import pox.openflow.libopenflow_01 as of

log = core.getLogger()


class LearningControllerPart1(object):
    def __init__(self, connection):
        # Keep track of the connection to the switch so that we can
        # send it messages!
        self.connection = connection

        # This binds our PacketIn event listener
        connection.addListeners(self)

        # Use this table to keep track of which ethernet address is on
        # which switch port (keys are MACs, values are ports).
        self.mac_to_port = {}

    def send_packet(self, buffer_id, raw_data, out_port, in_port):
        """
        Sends a packet out of the specified switch port.
        If buffer_id is a valid buffer on the switch, use that.    Otherwise,
        send the raw data in raw_data.
        The "in_port" is the port number that packet arrived on.    Use
        OFPP_NONE if you're generating this packet.
        """
        msg = of.ofp_packet_out()
        msg.in_port = in_port
        if buffer_id != -1 and buffer_id is not None:
            # We got a buffer ID from the switch; use that
            msg.buffer_id = buffer_id
        else:
            # No buffer ID from switch -- we got the raw data
            if raw_data is None:
                # No raw_data specified -- nothing to send!
                return
            msg.data = raw_data

        # Add an action to send to the specified port
        action = of.ofp_action_output(port=out_port)
        msg.actions.append(action)

        # Send message to switch
        self.connection.send(msg)

    def act_like_hub(self, packet, packet_in):
        """
        Implement hub-like behavior -- send all packets to all ports besides
        the input port.
        """

        # We want to output to all ports -- we do that using the special
        # OFPP_FLOOD port as the output port.    (We could have also used
        # OFPP_ALL.)
        self.send_packet(packet_in.buffer_id, packet_in.data,
                         of.OFPP_FLOOD, packet_in.in_port)

        # Note that if we didn't get a valid buffer_id, a slightly better
        # implementation would check that we got the full data before
        # sending it (len(packet_in.data) should be == packet_in.total_len)).

    def act_like_switch(self, packet, packet_in):
        # packet (ethernet)
        # packet_in (ofp_packet_in)

        # Learn the port for the source MAC
        src_mac = packet.src
        src_port = packet_in.in_port
        self.mac_to_port[src_mac] = src_port

        # If packet is multicast, flood it.
        if packet.dst.isMulticast():
            log.debug("Broadcast from {src}".format(src=src_mac))
            self.flood(packet, packet_in)
            return

        # Packet has only a single recipient.
        dst_mac = packet.dst
        dst_port = self.mac_to_port.get(dst_mac, None)
        # If we don't yet know the dst port, we flood the packet.
        if not dst_port:
            log.debug("Flooding unicast from {src} to {dst}".format(src=src_mac,
                                                                    dst=dst_mac))
            self.flood(packet, packet_in)
            return

        # We know dst port. U
        log.debug("Unicast from {src} to {dst}".format(src=src_mac,
                                                       dst=dst_mac))
        self.send_packet(packet_in.buffer_id, packet_in.data,
                         dst_port, packet_in.in_port)

    def flood(self, packet, packet_in):
        self.send_packet(packet_in.buffer_id, packet_in.data,
                         of.OFPP_FLOOD, packet_in.in_port)

    def _handle_PacketIn(self, event):
        """
        Handles packet in messages from the switch.
        """

        packet = event.parsed  # This is the parsed packet data.
        if not packet.parsed:
            log.warning("Ignoring incomplete packet")
            return

        packet_in = event.ofp  # The actual ofp_packet_in message.

        # Comment out the following line and uncomment the one after
        # when starting the exercise.
        self.act_like_switch(packet, packet_in)
        # self.act_like_switch(packet, packet_in)


def launch():
    """
    Starts the component
    """
    def start_switch(event):
        log.debug("Controlling %s" % (event.connection,))
        LearningControllerPart1(event.connection)

    core.openflow.addListenerByName("ConnectionUp", start_switch)
