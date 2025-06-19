# VLAN Configuration

## VLANs
- VLAN10: IoT (192.168.10.0/24)
- VLAN20: Guest (192.168.20.0/24)
- VLAN30: Personal (192.168.30.0/24)
- VLAN40: DMZ (192.168.40.0/24)

## Firewall Rules
- IoT → [BLOCK] → Personal, Guest, LAN
- Personal → [ALLOW] → IoT
- Guest → [BLOCK] → LAN, IoT, Personal; [ALLOW] → Internet
