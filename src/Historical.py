from logging import exception
import sqlite3
import socket, pickle, selectors, types, sys, os

#Neka glupost da bi mogo da importujem iz modela
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

from models.ETipZahteva import ETipZahteva
from models.ConnectionParams import HOST, DB_PORT, R_PORT
from models.IzvestajPoKorisniku import IzvestajKorisnik

#Instanca selektora za asinhroni rad soketa
sel = selectors.DefaultSelector()

#Konekcija sa SQLite DataBase
conn = sqlite3.connect('../data/dataBase.db')
cur = conn.cursor()

#Pravljenje Tabela u slucaju da ne postoje
cur.executescript('''
CREATE TABLE IF NOT EXISTS "Korisnici" (
    "brojilo"	INTEGER NOT NULL UNIQUE,
    "korisnik"	TEXT NOT NULL,
    "adresa"	TEXT NOT NULL,
    "grad"	TEXT NOT NULL,
    PRIMARY KEY("brojilo")
);
CREATE TABLE IF NOT EXISTS "Potrosnja" (
	"brojilo"	INTEGER,
	"potrosnja"	REAL NOT NULL CHECK("potrosnja" > 0),
	"mesec"	TEXT,
	PRIMARY KEY("brojilo","mesec"),
	FOREIGN KEY("brojilo") REFERENCES "Korisnici"("brojilo")
);
''')

#Primanje konekcije
def accept(sock):
    conn, addr = sock.accept() 
    print(f"Accepted connection from {addr}")
    conn.setblocking(False)
    data = types.SimpleNamespace(addr=addr, inb=b"", outb=b"")
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    sel.register(conn, events, data = data)

#Komunikacija sa korisnikom
def service_connection(key, mask):
    sock = key.fileobj
    data = key.data

    #print(f'Maska : {mask:04b}')
    
    if mask & selectors.EVENT_READ:
        #Primanje zahteva, zahtev nikad nece biti velik pa mogu da izbegnem vise primanja paketa
        recv_data = sock.recv(4096)
        if recv_data:
            #print('loading data')
            data.inb += recv_data
        else:
            print(f"Closing connection to {data.addr}")
            sel.unregister(sock)
            sock.close()

    if mask & selectors.EVENT_WRITE:
        #Obrada zahteva i odgovor
        if data.inb:
            work_data = pickle.loads(data.inb)
            #print(work_data)

            return_data = process_request(work_data[0],work_data[1])
            data.outb = pickle.dumps(return_data)

            data.inb = bytes()
        if data.outb:
            #print(f"Echoing {data.outb} to {data.addr}")            
            sent = sock.send(data.outb)
            data.outb = data.outb[sent:]
            if not data.outb:
                print(f"Closing connection to {data.addr}")
                sel.unregister(sock)
                sock.close()
                

#Obrada zahteva
def process_request(request, value):
    ret_val = -1

    match request:
        case ETipZahteva.KORISNIK:
            cur.execute('''
            select k.brojilo, adresa, grad, potrosnja, mesec
            from Korisnici k, Potrosnja p
            where k.brojilo = p.brojilo and k.korisnik = ?
            ''', (value, ))
            lista = cur.fetchall()
            potrosnje = list()
            brojilo, adresa, grad = lista[0][0], lista[0][1], lista[0][2]
            for item in lista:
                potrosnje.append((item[4],item[3]))
            return (value, IzvestajKorisnik(brojilo, adresa, grad, potrosnje))

        case ETipZahteva.MESEC:
            raise NotImplementedError

        case ETipZahteva.GRAD:
            raise NotImplementedError

        case ETipZahteva.ADD_USER:
            try:
                cur.execute('INSERT INTO Korisnici (brojilo, korisnik, adresa, grad) VALUES (?, ?, ?, ?)', (value[0],value[1], value[2], value[3]))
            except sqlite3.IntegrityError:
                return 'Korisnik sa prosldjenim brojilom vec postoji'
            conn.commit()
            ret_val = 'Uspesno dodato'

        case ETipZahteva.ADD_CON:
            raise NotImplementedError

        case ETipZahteva.REMOVE_USER:
            cur.execute('DELETE FROM Korisnici where brojilo = ?', (value, ))
            conn.commit()
            ret_val = f'Uspesno izbrisan korisnik sa brojilom({value})'
        
        case ETipZahteva.REMOVE_CON:
            raise NotImplementedError

        case ETipZahteva.GET_ALL_USERS:
            cur.execute('SELECT * FROM Korisnici')
            ret_val = cur.fetchall()

        case ETipZahteva.EXISTS_USER:
            cur.execute('SELECT * FROM Korisnici WHERE brojilo = ?', (value, ))
            findings = cur.fetchall()
            #print(findings)
            if len(findings) != 0:
                ret_val = True
            else:
                ret_val = False

        case ETipZahteva.DB_INSERTS:
            try:
                cur.executescript('''
                DELETE FROM Potrosnja;
                DELETE FROM Korisnici;

                INSERT INTO "Korisnici"("brojilo","korisnik","adresa","grad") VALUES (1234,'Stefan Scekic','Kozaracka 1','Novi Sad');
                INSERT INTO "Korisnici"("brojilo","korisnik","adresa","grad") VALUES (4568,'Sasa Kitic','Kozaracka 1','Novi Sad');
                INSERT INTO "Korisnici"("brojilo","korisnik","adresa","grad") VALUES (9812,'Dragana Banic','Kozaracka 1','Novi Sad');
                INSERT INTO "Korisnici"("brojilo","korisnik","adresa","grad") VALUES (7812,'Uros Petrov','Kozaracka 1','Novi Sad');
                INSERT INTO "Korisnici"("brojilo","korisnik","adresa","grad") VALUES (1111,'Ivan','Sindjeliceva 2','Kikinda');
                INSERT INTO "Korisnici"("brojilo","korisnik","adresa","grad") VALUES (5555,'Lidija Erceg','Contikarska 2A','Novi Sad');
                INSERT INTO "Korisnici"("brojilo","korisnik","adresa","grad") VALUES (6666,'Sasa','Heroja Pinkija 124','Novi Sad');

                INSERT INTO "Potrosnja"("brojilo", "potrosnja", "mesec") VALUES (1111, 240.5, 'JUN');
                INSERT INTO "Potrosnja"("brojilo", "potrosnja", "mesec") VALUES (1111, 120, 'JUL');
                INSERT INTO "Potrosnja"("brojilo", "potrosnja", "mesec") VALUES (1234, 220.5, 'JUN');
                INSERT INTO "Potrosnja"("brojilo", "potrosnja", "mesec") VALUES (4568, 220.2, 'JUN');
                INSERT INTO "Potrosnja"("brojilo", "potrosnja", "mesec") VALUES (4568, 500, 'JAN');
                INSERT INTO "Potrosnja"("brojilo", "potrosnja", "mesec") VALUES (9812, 450.98, 'JAN');
                INSERT INTO "Potrosnja"("brojilo", "potrosnja", "mesec") VALUES (9812, 600.112, 'FEB');
                INSERT INTO "Potrosnja"("brojilo", "potrosnja", "mesec") VALUES (7812, 516.4, 'MAR');
                INSERT INTO "Potrosnja"("brojilo", "potrosnja", "mesec") VALUES (5555, 312, 'MAR');
                INSERT INTO "Potrosnja"("brojilo", "potrosnja", "mesec") VALUES (6666, 437.88, 'APR');
                ''')
            except Exception as e:
                print(e)
                return 'Nesto je poslo po zlu'
            else:
                return 'Tabela uspesno izmenjena'

    return ret_val

def main():    
    #Kreacija soketa
    data_buffer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    reader_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    data_buffer_socket.bind((HOST, DB_PORT))
    reader_socket.bind((HOST, R_PORT))

    data_buffer_socket.listen()
    reader_socket.listen()

    data_buffer_socket.setblocking(False)
    reader_socket.setblocking(False)

    sel.register(data_buffer_socket, selectors.EVENT_READ, data=None)
    sel.register(reader_socket, selectors.EVENT_READ, data=None)
    #Slusanje 
    try:
        while True:
            events = sel.select(timeout=0)
            #print(events)
            for key, mask in events:
                #print(events)
                if key.data is None:
                    accept(key.fileobj)
                else:
                    service_connection(key, mask)
    except KeyboardInterrupt:                           #omogucava Ctrl+C prekid programa
        print("Caught keyboard interrupt, exiting")
    finally:
        sel.close()

if __name__ == "__main__":
    main()