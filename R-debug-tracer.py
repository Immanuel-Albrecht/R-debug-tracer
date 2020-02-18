#!/usr/bin/env python3

from subprocess import Popen, PIPE, STDOUT
from select import select
from time import sleep
import re
import sys

if len(sys.argv) != 2:
    print(f"Usage: {sys.argv[0]} [R-script]")
    print(f"  where")
    print(f"    [R-script]  is the path to an R script that starts debugging.")
    sys.exit()
    
with open(sys.argv[1],"rt") as f:
    write_buffer = f.read() + "\n"

R = Popen(["R","--no-save"],stdin=PIPE,stdout=PIPE,stderr=STDOUT)



prompt = re.compile(r"Browse\[([0-9]+)]>")
end_marker = re.compile(r"exiting from: debug_main()")

read_buffer = ""
rb_process_idx = 0

interactive_replies = ["where\n","s\n"]
reply_idx = 0

end_reply = "q()\n"

sleep(10)

while R.poll() is None:
    rlist,wlist,xlist = select([R.stdout],[R.stdin],[],1)
    # first, try to read all output of R (process might block if stdout buffer is full)
    if rlist:
        R_out = R.stdout.read1().decode()
        sys.stdout.write(R_out)
        sys.stdout.flush()
        read_buffer += R_out
        match = prompt.search(read_buffer[rb_process_idx:])
        if match:
            rb_process_idx += match.span()[1]
            depth = int(match.groups()[0])
            write_buffer += interactive_replies[reply_idx]
            reply_idx += 1
            if reply_idx >= len(interactive_replies):
                reply_idx = 0
        else:
            match = end_marker.search(read_buffer[rb_process_idx:])
            if match:
                rb_process_idx += match.span()[1]
                write_buffer += end_reply
        # throw away the used up read buffer
        read_buffer = read_buffer[rb_process_idx:]
        rb_process_idx = 0
        continue
    # when all is read, try to feed the contents of the write buffer into R
    if wlist and write_buffer:
        R.stdin.write(write_buffer[0].encode())
        write_buffer = write_buffer[1:]
        R.stdin.flush()
        continue
    # wait for further output
    sleep(.01)