import time

LOG_PATH = "Openssh/OpenSSH_2k.log"
LINHA = "Dec  4 04:47:44 host sshd[1234]: Failed password for invalid user root from 10.0.0.1 port 22 ssh2\n"
n1 = 0

if __name__ == "__main__":
    with open(LOG_PATH, "a", encoding="utf-8") as arquivo:
        while True:
            n1 += 1
            arquivo.write(LINHA)
            arquivo.flush()
            time.sleep(0.1)
            print(n1)