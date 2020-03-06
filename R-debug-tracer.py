#!/usr/bin/env python3

from subprocess import Popen, PIPE, STDOUT
from select import select
from time import sleep
import re
import sys

if len(sys.argv) != 2:
    print(f"Usage: {sys.argv[0]} [R-script] [--where]")
    print(f"  where")
    print(f"    [R-script]  is the path to an R script that starts debugging.")
    print(f"    --where     enable the where command on step-into. Nice for debugging.")
    sys.exit()
    
with open(sys.argv[1],"rt") as f:
    write_buffer = f.read() + "\n"

R = Popen(["R","--no-save"],stdin=PIPE,stdout=PIPE,stderr=STDOUT)


current_debug_command_marker = re.compile(r"debug(| at [^:]+): ")
prompt = re.compile(r"Browse\[([0-9]+)]>")
end_marker = re.compile(r"exiting from: debug_main\(\)")

sink_warning = re.compile(r"sink\(.*\)")

read_buffer = ""
rb_process_idx = 0

# a list of commands that are cycled throughout the debug session
interactive_replies = ["s\n"]
reply_idx = 0

command_start_marker = -1

last_depth = -1
# a list of scripted commands, that are issued whenever the depth in the promt
# increases: beware to only use commands that do not increase the depth here,
# or you have programmed yourself a nice little infinte recursion
depth_increase_replies = ["match.call(expand.dots=TRUE)\n",
                          "pryr::call_tree(match.call(expand.dots=TRUE),width=10000)\n"]

if "--where" in sys.argv[2:]:
    depth_increase_replies.append("where\n")

# command used to exit R :)
end_reply = "q()\n"

# this buffer holds the next scripted commands
reply_buffer = []

while R.poll() is None:
    rlist,wlist,xlist = select([R.stdout],[R.stdin],[],1)
    # first, try to read all output of R (process might block if stdout buffer is full)
    if rlist:
        R_out = R.stdout.read1(1024).decode() # read1(-1) is not supported on all platforms; technically, decode might fail, 
                                             # too, if we're in the middle of a multi-byte unicode character...
        sys.stdout.write(R_out)
        sys.stdout.flush()
        read_buffer += R_out
        match = current_debug_command_marker.search(read_buffer[rb_process_idx:])
        if match:
            command_start_marker = rb_process_idx + match.span()[-1]

        match = prompt.search(read_buffer[rb_process_idx:])
        if match: #we just read the interactive prompt, and we are going to react to it
            rb_process_idx += match.span()[1]
            if command_start_marker >= 0:
                current_debug_command = read_buffer[command_start_marker:rb_process_idx - (match.span()[1] - match.span()[0])]
                #
                # There is a minor glitch: sometimes, after 'debug:' there is a value printed,
                # which results in all kinds of errors and possibly also undefined behaviour...
                #
                # Browse[7]> s
                # exiting from: validmu(mu)
                # debugging in: valideta(eta)
                # debug: [1] TRUE
                # Browse[7]> pryr::call_tree( x=quote( ( [1] TRUE
                # Error: unexpected '[' in "pryr::call_tree( x=quote( ( ["
                # Browse[7]>  ) ), width=10000)
                # Error: unexpected ')' in " )"
                #
                # This will also cause more problems downstream, because we will then read additional prompts
                # and get out of sync with the scripted responses!
                # TODO: FIX ^^ THIS ^^
                #
                command_start_marker = -1
                if current_debug_command.strip():
                    reply_buffer.append("pryr::call_tree( x=quote( ( "+current_debug_command+" ) ), width=10000)\n")
                    
            depth = int(match.groups()[0])
            if depth > last_depth:
                reply_buffer.extend(depth_increase_replies)
            last_depth = depth
            if reply_buffer: # if there are still scripted replies, use one of them
                write_buffer += reply_buffer.pop(0)
            else: # no more scripted replies, cycle through the default commands
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
        if sink_warning.search(read_buffer[:rb_process_idx]):
            print(f"!!![TRACER]")
            print(f"!!![TRACER] WARNING: found sink(..) in R output")
            print(f"!!![TRACER]  PLEASE NOTE THAT CALLS TO sink (and other functions like capture.output) WILL INTERFERE WITH THE TRACE!")
            print(f"!!![TRACER]")
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
    sleep(.005)
