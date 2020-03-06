#!/usr/bin/env python3

from subprocess import Popen, PIPE, STDOUT
from select import select
from time import sleep
import re
import sys

if "--help" in sys.argv:
    print(f"Usage: {sys.argv[0]} [R-script] [--where]")
    print(f"  where")
    print(f"    [R-script]   is the path to an R script that starts debugging.")
    print(f"    --where      enable the where command on step-into. Nice for debugging.")
    print(f"    --just-warn  only warn when we find a call to sink")
    sys.exit()
    
with open(sys.argv[1],"rt") as f:
    write_buffer = f.read() + "\n"

R = Popen(["R","--no-save"],stdin=PIPE,stdout=PIPE,stderr=STDOUT)


current_debug_command_marker = re.compile(r"^debug(| at [^:]+): ",re.MULTILINE)
prompt = re.compile(r"^(\+ |Browse\[([0-9]+)]> )",re.MULTILINE)
begin_marker = re.compile(r"^debugging in: debug_main\(\)",re.MULTILINE)
end_marker = re.compile(r"^exiting from: debug_main\(\)",re.MULTILINE)

malformed_debug_info = re.compile(r'^\[1\] (TRUE|FALSE|".*"|[0-9])')


sink_warning = re.compile(r"^debugging in: sink\(.*\)",re.MULTILINE)

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

# Do not start emitting commands until we say go:
do_debug = False

# Keep track whether we have finnished processing
process_input = False

def split_lines(s):
    l0 = s.split("\n")
    if l0[-1] == "":
        l0 = l0[:-1]
    return [x+"\n" for x in l0]


while R.poll() is None:
    rlist,wlist,xlist = select([R.stdout],[R.stdin],[],0 if process_input else 1)
    # first, try to read all output of R (process might block if stdout buffer is full)
    if rlist:
        R_out = R.stdout.read1(1024).decode() # read1(-1) is not supported on all platforms; technically, decode might fail, 
                                             # too, if we're in the middle of a multi-byte unicode character...
        sys.stdout.write(R_out)
        sys.stdout.flush()
        read_buffer += R_out
        process_input = True
        
    if process_input:
        process_input = False
        match = current_debug_command_marker.search(read_buffer[rb_process_idx:])
        if match:
            command_start_marker = rb_process_idx + match.span()[-1]
        match = begin_marker.search(read_buffer[rb_process_idx:])
        if match:
            # We found the entry point of the tracing session
            rb_process_idx += match.span()[1]
            do_debug = True
            process_input = True
        else:
            match = prompt.search(read_buffer[rb_process_idx:])
            if match: #we just read the interactive prompt, and we are going to react to it
                process_input = True
                rb_process_idx += match.span()[1]
                if match.groups()[0] == "+ ":
                    if reply_buffer: # if there are still scripted replies, use one of them
                        write_buffer += reply_buffer.pop(0)
                    else:
                        # Looks like that the reply buffer contained an incomplete command
                        write_buffer += "\x03" #CTRL+C to recover to the prompt
                else:
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
                        # We might want to capture this with some smart regular expression.
                        #
                        command_start_marker = -1
                        if current_debug_command.strip():
                            if not malformed_debug_info.match(current_debug_command):
                                reply_buffer.extend(
                                    split_lines("pryr::call_tree( x=quote( ( \n"+current_debug_command+" ) ), width=10000)\n")
                                )
                            
                    depth = int(match.groups()[1])
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
                    process_input = True
                    rb_process_idx += match.span()[1]
                    write_buffer += end_reply
                    
        # throw away the used up read buffer
        if sink_warning.search(read_buffer[:rb_process_idx]):
            print(f"\n!!![TRACER]")
            print(f"!!![TRACER] WARNING: found sink(..) in R output")
            print(f"!!![TRACER]  PLEASE NOTE THAT CALLS TO sink (and other functions like capture.output) WILL INTERFERE WITH THE TRACE!")
            print(f"!!![TRACER]")
            if not "--just-warn" in sys.argv[2:]:
                sys.exit(1)
        read_buffer = read_buffer[rb_process_idx:]
        rb_process_idx = 0
        continue
    # when all is read, try to feed the contents of the write buffer into R
    if wlist and write_buffer:
        R.stdin.write(write_buffer[0].encode())
        write_buffer = write_buffer[1:]
        R.stdin.flush()
        continue
    if write_buffer and not wlist:
        waiting_to_write = True
    else:
        waiting_to_write = False
    # wait for further output
    sleep(.005)
