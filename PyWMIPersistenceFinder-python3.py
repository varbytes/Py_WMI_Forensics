#!/usr/bin/env python
# 
# PyWMIPersistenceFinder.py
# Version 1.1
#
# Original Author:
#   David Pany - Mandiant (FireEye) - 2017
#   Twitter: @DavidPany
#   Please send  comments, bug reports, and questions to @DavidPany
#       or push changes directly to GitHub
#
# Usage:
#   PyWMIPersistenceFinder.py <OBJECTS.DATA file>
#
#   The output is text based in the following format for each binding:
#       <consumer name>-<filter name>
#               <optional notes>
#           Consumer: <consumer name><consumer execution details>
#           Filter: <filter name><filter listener details>
#
# Execution time:
#   Execution time has been reported from 10 seconds to 5 minutes depending on input size.
#
# Description:
#   PyWMIPersistenceFinder.py is designed to find WMI persistence via FitlerToConsumerBindings
#   solely by keyword searching the OBJECTS.DATA file without parsing the full WMI repository.
#
#   In testing, this script has found the exact same data as python-cim's
#   show_FilterToConsumerBindings.py without requiring the setup. Only further testing will
#   indicate if this script misses any data that python-cim can find.
#
#   In theory, this script will detect FilterToConsumerBindings that are deleted and remain
#   in unallocated WMI space, but I haven't had a chance to test yet.
#
# Terms:
#   Event Filter:
#       Basically a condition that WMI is waiting for
#
#   Event Consumer:
#       Basically something that will happen such as script/file execution
#
#   Filter To Consumer Binding:
#       Structure that says "When filter condition happens, execute consumer"
#
# Changes:
#   1.1 - removed newline characters for regex matching
#       - enhanced txt output for readability
#   2.1 - [varbytes] updated regex strings to byte strings for Python 3 compatibility
#
# Future Improvements:
#   [ ] Implement named regex groups for clarity
#   [ ] Add CSV output option
#   [ ] Add input option for a directory of objects.data files
#
# References:
#   https://github.com/fireeye/flare-wmi/tree/master/python-cim
#   https://www.fireeye.com/content/dam/fireeye-www/global/en/current-threats/pdfs/wp-windows-management-instrumentation.pdf
#
# License:
#   Copyright (c) 2017 David Pany
#
#   Permission is hereby granted, free of charge, to any person obtaining a copy
#   of this software and associated documentation files (the "Software"), to deal
#   in the Software without restriction, including without limitation the rights
#   to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#   copies of the Software, and to permit persons to whom the Software is
#   furnished to do so, subject to the following conditions:
#
#   The above copyright notice and this permission notice shall be included in
#   all copies or substantial portions of the Software.
#
#   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#   LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#   OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#   SOFTWARE.
#

from __future__ import print_function
import sys
import re
import string
import locale

PRINTABLE_CHARS = set(string.printable)

def main():
    """Main function for everything!"""

    print("\n    Enumerating FilterToConsumerBindings...")

    #Read objects.data 4 lines at a time to look for bindings
    objects_file = open(sys.argv[1], "rb")
    current_line = objects_file.readline()
    lines_list = [current_line]
    current_line = objects_file.readline()
    lines_list.append(current_line)
    current_line = objects_file.readline()
    lines_list.append(current_line)
    current_line = objects_file.readline()
    lines_list.append(current_line)

    #Precompiled match objects to search each line with
    event_consumer_mo = re.compile(rb"([\w\_]*EventConsumer\.Name\=\")([\w\s]*)(\")")
    event_filter_mo = re.compile(rb"(_EventFilter\.Name\=\")([\w\s]*)(\")")

    #Dictionaries that will store bindings, consumers, and filters
    bindings_dict = {}
    consumer_dict = {}
    filter_dict = {}

    while current_line:
        # Join all the read lines together (should always be 4) to look for bindings spread over
        #   multiple lines that may have been one page
        potential_page = b" ".join(lines_list)

        # Look for FilterToConsumerBindings
        if b"_FilterToConsumerBinding" in potential_page:
            if (
                    re.search(event_consumer_mo, potential_page) and
                    re.search(event_filter_mo, potential_page)):
                event_consumer_name = re.search(event_consumer_mo, potential_page).groups(0)[1]
                event_filter_name = re.search(event_filter_mo, potential_page).groups(0)[1]

                #Add the consumers and filters to their dicts if they don't already exist
                #set() is used to avoid duplicates as we go through the lines
                if event_consumer_name not in consumer_dict:
                    consumer_dict[event_consumer_name] = set()
                if event_filter_name not in filter_dict:
                    filter_dict[event_filter_name] = set()

                #Give the binding a name and add it to the dict
                binding_id = (b"%b-%b" % (event_consumer_name, event_filter_name)).decode()
                if binding_id not in bindings_dict:
                    bindings_dict[binding_id] = {
                        "event_consumer_name":event_consumer_name,
                        "event_filter_name":event_filter_name}

        # Increment lines and look again
        current_line = objects_file.readline()
        lines_list.append(current_line)
        lines_list.pop(0)

    # Close the file and look for consumers and filters
    objects_file.close()
    print("    {} FilterToConsumerBinding(s) Found. Enumerating Filters and Consumers..."
          .format(len(bindings_dict)))

    # Read objects.data 4 lines at a time to look for filters and consumers
    objects_file = open(sys.argv[1], "rb")
    current_line = objects_file.readline()
    lines_list = [current_line]
    current_line = objects_file.readline()
    lines_list.append(current_line)
    current_line = objects_file.readline()
    lines_list.append(current_line)
    current_line = objects_file.readline()
    lines_list.append(current_line)

    while current_line:
        potential_page = b" ".join(lines_list).replace(b"\n", b"")

        # Check each potential page for the consumers we are looking for
        if b"EventConsumer" in potential_page:
            for event_consumer_name, event_consumer_details in consumer_dict.items():
                # Can't precompile regex because it is dynamically created with each consumer name
                if b"CommandLineEventConsumer" in potential_page:
                    consumer_mo = re.compile(b"(CommandLineEventConsumer)(\x00\x00)(.*?)(\x00)(.*?)"
                                             b"(%b)(\x00\x00)?([^\x00]*)?" % event_consumer_name)
                    consumer_match = re.search(consumer_mo, potential_page)
                    if consumer_match:
                        noisy_string = consumer_match.groups()[2]
                        consumer_details = b"\n\t\tConsumer Type: {}\n\t\tArguments:     {}".format(
                            consumer_match.groups()[0],
                            filter(lambda event_consumer_name: event_consumer_name in
                                   PRINTABLE_CHARS, noisy_string))
                        if consumer_match.groups()[5]:
                            consumer_details += b"\n\t\tConsumer Name: {}".format(consumer_match.groups()[5])
                        if consumer_match.groups()[7]:
                            consumer_details += b"\n\t\tOther:         {}".format(consumer_match.groups()[7])
                        consumer_dict[event_consumer_name].add(consumer_details)

                else:
                    consumer_mo = re.compile(
                        rb"(\w*EventConsumer)(.*?)(%b)(\x00\x00)([^\x00]*)(\x00\x00)([^\x00]*)" % event_consumer_name)
                    consumer_match = re.search(consumer_mo, potential_page)
                    if consumer_match:
                        consumer_details = b"%b ~ %b ~ %b ~ %b" % (
                            consumer_match.groups()[0],
                            consumer_match.groups()[2],
                            consumer_match.groups()[4],
                            consumer_match.groups()[6])
                        consumer_dict[event_consumer_name].add(consumer_details)

        # Check each potential page for the filters we are looking for
        for event_filter_name, event_filter_details in filter_dict.items():
            if event_filter_name in potential_page:
                # Can't precompile regex because it is dynamically created with each filter name
                filter_mo = re.compile(
                    rb"(%b)(\x00\x00)([^\x00]*)(\x00\x00)" % event_filter_name)
                filter_match = re.search(filter_mo, potential_page)
                if filter_match:
                    filter_details = b"\n\t\tFilter name:  %b\n\t\tFilter Query: %b" % (
                        filter_match.groups()[0],
                        filter_match.groups()[2])
                    filter_dict[event_filter_name].add(filter_details)

        current_line = objects_file.readline()
        lines_list.append(current_line)
        lines_list.pop(0)
    objects_file.close()
    
    # Print results to stdout. CSV will be in future version.
    print("\n    Bindings:\n")
    for binding_name, binding_details in bindings_dict.items():
        if (
                "BVTConsumer-BVTFilter" in binding_name or
                "SCM Event Log Consumer-SCM Event Log Filter" in binding_name):
            print(
                "        {}\n                (Common binding based on consumer and filter names,"
                " possibly legitimate)".format(binding_name))
        else:
            print("        {}".format(binding_name))
        event_filter_name = binding_details["event_filter_name"]
        event_consumer_name = binding_details["event_consumer_name"]

        # Print binding details if available
        if consumer_dict[event_consumer_name]:
            for event_consumer_details in consumer_dict[event_consumer_name]:
                print("            Consumer: {}".format(event_consumer_details.decode(locale.getpreferredencoding())))
        else:
            print("            Consumer: {}".format(event_consumer_name.decode(locale.getpreferredencoding())))

        # Print details for each filter found for this filter name
        for event_filter_details in filter_dict[event_filter_name]:
            print("\n            Filter: {}".format(event_filter_details.decode(locale.getpreferredencoding())))
            print()

    # Print closing message
    print("\n    Thanks for using PyWMIPersistenceFinder! Please contact @DavidPany with "
          "questions, bugs, or suggestions.\n\n    Please review FireEye's whitepaper "
          "for additional WMI persistence details:\n        https://www.fireeye.com/content/dam"
          "/fireeye-www/global/en/current-threats/pdfs/wp-windows-management-instrumentation.pdf")

if __name__ == "__main__":
    main()

