#! /usr/bin/env python3

import ldap3
from pathlib import Path
from datetime import date
from optparse import OptionParser
from colorama import Fore, Back, Style
from multiprocessing import Lock, Pool, cpu_count
from time import strftime, localtime, time

status_color = {
    '+': Fore.GREEN,
    '-': Fore.RED,
    '*': Fore.YELLOW,
    ':': Fore.CYAN,
    ' ': Fore.WHITE
}

port = 389
ssl = True
lock = Lock()
server_info_directory_name = "info"

def display(status, data, start='', end='\n'):
    print(f"{start}{status_color[status]}[{status}] {Fore.BLUE}[{date.today()} {strftime('%H:%M:%S', localtime())}] {status_color[status]}{Style.BRIGHT}{data}{Fore.RESET}{Style.RESET_ALL}", end=end)

def get_arguments(*args):
    parser = OptionParser()
    for arg in args:
        parser.add_option(arg[0], arg[1], dest=arg[2], help=arg[3])
    return parser.parse_args()[0]

def checkAnonymousBind(server, port, use_ssl):
    t1 = time()
    try:
        server = ldap3.Server(server, port=port, use_ssl=use_ssl, get_info=ldap3.ALL)
        connection =ldap3.Connection(server)
        bind_status = connection.bind()
        t2 = time()
        return bind_status, server.info, t2-t1
    except Exception as error:
        t2 = time()
        return error, '', t2-t1
def checkAnonymousBind_Handler(thread_index, servers, port, use_ssl):
    successful_binds = {}
    for server in servers:
        status = checkAnonymousBind(server, port, use_ssl)
        if status[0] == True:
            successful_binds[server] = status[1]
            with lock:
                display(' ', f"Thread {thread_index+1}:{status[2]:.2f}s -> {Fore.CYAN}{server}{Fore.RESET} => {Back.MAGENTA}{Fore.BLUE}Authorized{Fore.RESET}{Back.RESET}")
        elif status[0] == False:
            with lock:
                display(' ', f"Thread {thread_index+1}:{status[2]:.2f}s -> {Fore.CYAN}{server}{Fore.RESET} => {Back.RED}{Fore.YELLOW}Access Denied{Fore.RESET}{Back.RESET}")
        else:
            with lock:
                display(' ', f"Thread {thread_index+1}:{status[2]:.2f}s -> {Fore.CYAN}{server}{Fore.RESET} => {Fore.YELLOW}Error Occured : {Back.RED}{status[0]}{Fore.RESET}{Back.RESET}")
    return successful_binds
def main(servers, port, use_ssl):
    successful_binds = {}
    thread_count = cpu_count()
    pool = Pool(thread_count)
    display('+', f"Starting {Back.MAGENTA}{thread_count} Threads{Back.RESET}")
    threads = []
    total_servers = len(servers)
    server_divisions = [servers[group*total_servers//thread_count: (group+1)*total_servers//thread_count] for group in range(thread_count)]
    for index, server_division in enumerate(server_divisions):
        threads.append(pool.apply_async(checkAnonymousBind_Handler, (index, server_division, port, use_ssl, )))
    for thread in threads:
        successful_binds.update(thread.get())
    pool.close()
    pool.join()
    display('+', f"Threads Finished Excuting")
    return successful_binds

if __name__ == "__main__":
    cwd = Path.cwd()
    server_info_directory = Path.mkdir(cwd / server_info_directory_name, exist_ok=True)
    arguments = get_arguments(('-s', "--server", "server", "Target LDAP Servers (seperated by ',' or File Name containing Targets)"),
                              ('-p', "--port", "port", f"Port of Target LDAP Servers (Default={port})"),
                              ('-S', "--ssl", "ssl", f"Use SSL (True/False, Default={ssl})"),
                              ('-w', "--write", "write", "File to Dump Successful Logins (default=current data and time)"))
    if not arguments.server:
        display('-', f"Please specify {Back.YELLOW}Target Server{Back.RESET}")
        exit(0)
    else:
        try:
            with open(arguments.server, 'r') as file:
                arguments.server = [server for server in file.read().split('\n') if server != '']
        except FileNotFoundError:
            arguments.server = arguments.server.split(',')
        except Exception as error:
            display('-', f"Error Occured while reading File {Back.MAGENTA}{arguments.server}{Back.RESET} => {Back.YELLOW}{error}{Back.RESET}")
            exit(0)
    arguments.port = port if not arguments.port else int(arguments.port)
    arguments.ssl = False if arguments.ssl == "False" else ssl
    if not arguments.write:
        arguments.write = f"{date.today()} {strftime('%H_%M_%S', localtime())}.txt"
    t1 = time()
    successful_anonymous_binds = main(arguments.server, arguments.port, arguments.ssl)
    t2 = time()
    display(':', f"Successful Binds = {Back.MAGENTA}{len(successful_anonymous_binds)}{Back.RESET}")
    display(':', f"Time Taken       = {Back.MAGENTA}{t2-t1:.2f} seconds{Back.RESET}")
    display(':', f"Rate             = {Back.MAGENTA}{len(arguments.server)/(t2-t1):.2f} servers / second{Back.RESET}")
    display(':', f"Dumping Successful Binds to File {Back.MAGENTA}{arguments.write}{Back.RESET} and Server Information to {Back.MAGENTA}{server_info_directory_name}{Back.RESET} directory")
    with open(arguments.write, 'w') as file:
        for server, server_info in successful_anonymous_binds.items():
            file.write(f"{server}\n")
            with open(f"{server_info_directory_name}/{server}", 'w') as info_file:
                info_file.write(str(server_info))
    display('+', f"Dumped Successful Logins to File {Back.MAGENTA}{arguments.write}{Back.RESET} and Server Information to {Back.MAGENTA}{server_info_directory_name}{Back.RESET} directory")