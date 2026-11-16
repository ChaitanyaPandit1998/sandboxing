#!/bin/sh
# Fixed transport for browser PTYs. Never expose SSH local escapes or forwarding.
exec /usr/bin/ssh -e none \
  -o EnableEscapeCommandline=no \
  -o PermitLocalCommand=no \
  -o ForwardAgent=no \
  -o ForwardX11=no \
  -o ClearAllForwardings=yes "$@"
