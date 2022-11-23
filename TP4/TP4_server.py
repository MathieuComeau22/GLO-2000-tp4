import email
import email.message
import hashlib
import json
import os
import re
import select
import smtplib
import socket
from typing import NoReturn, Optional

from ModulesTP import glosocket
import TP4_utils


class Server:

    def __init__(self) -> None:
        """
        Cette méthode est automatiquement appelée à l’instanciation du serveur, elle doit :
        - Initialiser le socket du serveur et le mettre en écoute. 
        - Créer le dossier des données pour le serveur dans le dossier courant s’il n’existe pas. 
        - Préparer deux listes vides pour les sockets clients.
        - Compiler un pattern Regex qui sera utilisé pour vérifier les adresses courriel.

        Attention : ne changez pas le nom des attributs fournis, ils sont utilisés dans les tests. 
        Vous pouvez cependant ajouter des attributs supplémentaires.
        """
        # Socket TCP IPv4 en mode écoute sur le port TP4_utils.SOCKET_PORT
        self._server_socket = self.make_server_socket()

        # initialisation des deux listes pour les sockets clients
        self._client_socket_list: list[socket.socket] = []
        self._connected_client_list: list[socket.socket] = []
        self._client_info_dict = {}

        self._server_data_path = os.path.join(os.getcwd(), TP4_utils.SERVER_DATA_DIR)
        self._server_lost_path = os.path.join(os.getcwd(), TP4_utils.SERVER_LOST_DIR)
        self._server_lost_txt_path = os.path.join(self._server_lost_path, "LOST.txt")
        self._create_file(self._server_data_path)
        self._create_file(self._server_lost_path)

        if not os.path.exists(self._server_lost_txt_path) :
            with open(self._server_lost_txt_path, 'w') as f:
                myInitJson = {
                    'emails': []
                }
                f.write(json.dumps(myInitJson))

        self._email_verificator = re.compile(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)")

    def _recv_data(self, source: socket.socket) -> Optional[TP4_utils.GLO_message]:
        """
        Cette méthode utilise le module glosocket pour récupérer un message.
        Elle doit être appelée systématiquement pour recevoir des données d’un client.

        Le message attendu est une chaine de caractère représentant un JSON 
        valide, qui est décodé avec le module json. Si le JSON est invalide, 
        s’il ne représente pas un dictionnaire du format GLO_message, ou si 
        le résultat est None, le socket client est fermé et retiré des listes.
        """
        message = glosocket.recv_msg(source)

        if message:
            myDict = TP4_utils.GLO_message(json.loads(message))
            try:
                if myDict["header"] is None or myDict["data"] is None:
                    if source in self._client_socket_list:
                        self._client_socket_list.remove(source)
                    if source in self._connected_client_list:
                        self._connected_client_list.remove(source)
                    source.close()
                else:
                    return myDict
            except Exception as e:
                print(f"Error: {e}")

        else:
            if source in self._client_socket_list:
                self._client_socket_list.remove(source)
            if source in self._connected_client_list:
                self._connected_client_list.remove(source)
            source.close()

    def _main_loop(self) -> None:
        """
        Boucle principale du serveur.

        Le serveur utilise le module select pour récupérer les sockets en 
        attente puis appelle l’une des méthodes _accept_client, _process_client
        ou _authenticate_client pour chacun d’entre eux.
        """
        waiting_list, _, _ = select.select(
        [self._server_socket] + self._client_socket_list, [], [])

        for waiter in waiting_list:
            if (waiter == self._server_socket):
                self._accept_client()
            else:
                if waiter in self._connected_client_list:
                    self._process_client(waiter)
                else:
                    self._authenticate_client(waiter)

    def _accept_client(self) -> None:
        """
        Cette méthode accepte une connexion avec un nouveau socket client et 
        l’ajoute aux listes appropriées.
        """
        socket_client,_ = self._server_socket.accept()
        self._client_socket_list.append(socket_client)

    def _authenticate_client(self, client_socket: socket.socket) -> None:
        """
        Cette méthode traite les demandes de création de comptes et de connexion.

        Si les données reçues sont invalides, la méthode retourne immédiatement.
        Sinon, la méthode traite la requête et répond au client avec un JSON
        conformant à la classe d’annotation GLO_message. Si nécessaire, le client
        est également ajouté aux listes appropriées.
        """
        donnees = self._recv_data(client_socket)
        condition = True
        username = donnees["data"]["username"].lower()
        password = hashlib.sha384(donnees["data"]["password"].encode()).hexdigest()
        if donnees["header"] == TP4_utils.message_header.AUTH_LOGIN:
            # verifier si username et password correspondent 
            try:
                with open(os.path.join(self._server_data_path, username, "passwd.txt"), 'r') as f:
                    if (f.readline() != password):
                        condition = False
                    else:
                        self._connected_client_list.append(client_socket)               
            except Exception:
                condition = False 

        elif donnees["header"] == TP4_utils.message_header.AUTH_REGISTER:
            self._create_file(os.path.join(self._server_data_path, username))
            filepath = os.path.join(self._server_data_path, username, "passwd.txt")
            with open(filepath, 'w') as f:
                f.write(password)
            filepath = os.path.join(self._server_data_path, username, "emails.txt")
            with open(filepath, 'w') as f:
                myInitJson = {
                    'emails': []
                }
                f.write(json.dumps(myInitJson))
            self._connected_client_list.append(client_socket)

        else:
            condition = False

        if condition:
            glosocket.send_msg(client_socket, json.dumps(TP4_utils.GLO_message({'header': TP4_utils.message_header.OK, 'data': ''})))
        else:
            glosocket.send_msg(client_socket, json.dumps(TP4_utils.GLO_message({'header': TP4_utils.message_header.ERROR, 'data': ''})))
        

    def _process_client(self, client_socket: socket.socket) -> None:
        """
        Cette méthode traite les commandes d’utilisateurs connectés.

        Si les données reçues sont invalides, la méthode retourne immédiatement.
        Sinon, la méthode traite la requête et répond au client avec un JSON
        conformant à la classe d’annotation GLO_message.
        """
        donnees = self._recv_data(client_socket)
        if donnees == None:
            if client_socket in self._client_socket_list:
                self._client_socket_list.remove(client_socket)
            if client_socket in self._connected_client_list:
                self._connected_client_list.remove(client_socket)
            client_socket.close()
            #glosocket.send_msg(client_socket, json.dumps(TP4_utils.GLO_message({'header': TP4_utils.message_header.OK, 'data': ''})))

        elif donnees["header"] == TP4_utils.message_header.INBOX_READING_REQUEST:
            glosocket.send_msg(client_socket, json.dumps(self._get_subject_list(donnees["data"])))
            
        elif donnees["header"] == TP4_utils.message_header.INBOX_READING_CHOICE:
            # Pas sur de comprendre ici
            glosocket.send_msg(client_socket, json.dumps(self._get_email(donnees["data"])))

        elif donnees["header"] == TP4_utils.message_header.EMAIL_SENDING:
            glosocket.send_msg(client_socket, json.dumps(self._send_email(donnees["data"])))

        elif donnees["header"] == TP4_utils.message_header.STATS_REQUEST:
            glosocket.send_msg(client_socket, json.dumps(self._get_stats(donnees["data"]["username"])))
            
        else:
            pass

    def _get_subject_list(self, username: str) -> TP4_utils.GLO_message:
        """
        Cette méthode récupère la liste des courriels d’un utilisateur.

        Le GLO_message retourné contient dans le champ "data" une liste
        de chaque sujet, sa source et un numéro (commence à 1).
        Si le nom d’utilisateur est invalide, le GLO_message retourné 
        indique l’erreur au client.
        """
        try:
            emailJson = self._read_user_file(username)
            emails = emailJson["emails"]
            counter = 1
            returnList = []
            for email in emails:
                number = counter
                subject = email["subject"]
                source = email["Source"]
                returnList.append(TP4_utils.SUBJECT_DISPLAY.format(number=number, subject=subject, source=source))
                counter += 1
        except Exception as e:
            print(f"Get subject list error: {e}")
            message = {
                'header': TP4_utils.message_header.ERROR,
                'data': []
            }
            return TP4_utils.GLO_message(message)
        print(returnList)
        message = {
            'header': TP4_utils.message_header.OK,
            'data': returnList
        }    
        return TP4_utils.GLO_message(message)

    def _get_email(self, data: dict) -> TP4_utils.GLO_message:
        """
        Cette méthode récupère le contenu du courriel choisi par l’utilisateur.

        Le GLO_message retourné contient dans le champ « data » la représentation
        en chaine de caractère du courriel chargé depuis le fichier à l’aide du 
        module email. Si le choix ou le nom d’utilisateur est incorrect, le 
        GLO_message retourné indique l’erreur au client.
        """
        try:
            jsonReturn = {}
            username = data["username"]
            choice = data["mailNumber"]

            emailJson = self._read_user_file(username)
            emails = emailJson["emails"]
            emailWanted = emails[int(choice)-1]
            print(emailWanted)
            jsonReturn["source"] = emailWanted["Source"]
            jsonReturn["subject"] = emailWanted["subject"]
            jsonReturn["content"] = emailWanted["content"]
            jsonReturn["destination"] = f"{username}@{TP4_utils.SERVER_DOMAIN}"

            message = {
                "header": TP4_utils.message_header.OK,
                "data": jsonReturn
            }
            return TP4_utils.GLO_message(message)
        except Exception as e:
            print(f"get email error: {e}" )
            message = {
                "header": TP4_utils.message_header.ERROR,
                "data": ""
            }
            return TP4_utils.GLO_message(message)

    def _send_email(self, email_string: str) -> TP4_utils.GLO_message:
        """
        Cette méthode envoie un courriel local ou avec le serveur SMTP.

        Avant l’envoi, le serveur doit vérifier :
        - Les adresses courriel source et destination,
        - La source est un utilisateur existant.

        Selon le domaine de la destination, le courriel est envoyé à
        l’aide du serveur SMTP de l’université où il est écrit dans
        le dossier de destination.

        Le GLO_message retourné contient indique si l’envoi a réussi
        ou non.
        """
        message = email.message.EmailMessage()
        jsonEmail = {}
        jsonUsed = {'emails': []}


        body_lines = """"""
        listEmail = email_string.split('\n')
        condition = True
        for ligne in listEmail:
            if condition:
                data = ligne.split(":")
                header = data[0]
                value = data[1]
                # DATA[0] EST MON HEADER, DATA[1] MA VALUE
                if header == "From":        
                    if self._email_verificator.fullmatch(value) is not None:
                        message["From"] = value
                        jsonEmail["Source"] = value
                    else:
                        pass
                    message["From"] = value
                    jsonEmail["Source"] = value
                elif header == "To":
                    if self._email_verificator.fullmatch(value) is  not None:
                        message["To"] = value
                        username = value.split("@")[0]
                        domaine = value.split("@")[1]
                    else:
                        pass
                    message["To"] = value
                    username = value.split("@")[0]
                    domaine = value.split("@")[1]

                elif header == "Subject":
                    message["Subject"] = value
                    jsonEmail["subject"] = value

                elif header == "MIME-Version":
                    condition = False
            else:
                body_lines += ligne + os.linesep 

        message.set_content(body_lines)
        jsonEmail["content"] = body_lines
        username = username.strip(" ").lower()
        domaine = domaine.strip(" ")

        if domaine == TP4_utils.SERVER_DOMAIN:
            # INTERNE
            if self._read_user_file(username) == {}:
                # USER N'EXISTE PAS DANS BANQUE
                file = open(self._server_lost_txt_path, "r", encoding="utf8")
                jsonfile = json.loads(file.read())
                file.close()
                
                if jsonfile == {}:
                    jsonfile["emails"] = []
                jsonEmail["destination"] = f"{username}@{domaine}"
                jsonfile["emails"].append(jsonEmail)
                self._write_user_file(self._server_lost_txt_path, jsonfile)

                message = {
                    'header': TP4_utils.message_header.ERROR,
                    'data': TP4_utils.SERVER_LOST_DIR
                }
                return TP4_utils.GLO_message(message)
                
            else:
                # USER EXISTE
                jsonfile = self._read_user_file(username)
                if jsonfile == {}:
                    print("aucun email dans ce compte...")
                    jsonfile["emails"] = []
                jsonfile["emails"].append(jsonEmail)
                self._write_user_file(os.path.join(self._server_data_path, username, "emails.txt"), jsonfile)
                message = {
                    'header': TP4_utils.message_header.OK,
                    'data': ''
                }
                return TP4_utils.GLO_message(message)
                
        else:
            # EXTERNE
            try:
                with smtplib.SMTP(host=TP4_utils.SMTP_SERVER, timeout=10) as connexion:
                    connexion.send_message(message)
                    message = {
                        'header': TP4_utils.message_header.OK,
                        'data': ''
                    }
                    return TP4_utils.GLO_message(message)
            except smtplib.SMTPException or socket.timeout:
                message = {
                    'header': TP4_utils.message_header.ERROR,
                    'data': ''
                }
                return TP4_utils.GLO_message(message)

    def _get_stats(self, username: str) -> TP4_utils.GLO_message:
        """
        Cette méthode récupère les statistiques liées à un utilisateur.

        Le GLO_message retourné contient dans le champ « data » les entrées :
        - « count », avec le nombre de courriels,
        - « folder_size », avec la taille totale du dossier en octets.
        Si le nom d’utilisateur est invalide, le GLO_message retourné 
        indique l’erreur au client.
        """
        data = self._read_user_file(username)

        folder_size = os.stat(os.path.join(self._server_data_path, username, "emails.txt")).st_size + os.stat(os.path.join(self._server_data_path, username, "passwd.txt")).st_size


        if data and data != {} :
            message = {
                "header": TP4_utils.message_header.OK,
                "data": {"count": len(data["emails"]), "folder_size": folder_size}
            }
            return TP4_utils.GLO_message(message)
        else :
            message = {
                "header": TP4_utils.message_header.ERROR,
                "data": "Erreur : Mauvais nom d'utilisateur."
            }
            return TP4_utils.GLO_message(message)


    """
    
    ICI, ON A LES FONCTIONS QUI NOUS AIDENT A SIMPLIFIER LE CODE
    
    """
    def _create_file(self, path: str) -> None:
        try:
            os.mkdir(path)
        except Exception:
            pass
        return

    def _read_user_file(self, username: str) -> json:
        try:
            file = open(os.path.join(self._server_data_path, username, "emails.txt"), "r", encoding="utf8")
            data = json.loads(file.read())
            file.close()
            return data
        except Exception as e:
            print(e)
            return {}

    def _write_user_file(self, path: str, data: dict) -> bool:
        try:
            file = open(path, "w", encoding="utf8")
            data = json.dumps(data)
            file.write(data)
            file.close()
            return True
        except Exception:
            print("error_write_user_file")
            return False

    def make_server_socket(self) -> socket.socket:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('localhost', TP4_utils.SOCKET_PORT))
        server_socket.listen()
        print(f"Listening on port {TP4_utils.SOCKET_PORT}")
        return server_socket

    def run(self) -> NoReturn:
        """
        Appelle la méthode _main_loop en boucle jusqu’à la fin du programme.
        """
        while True:
            self._main_loop()


def main() -> NoReturn:
    Server().run()


if __name__ == "__main__":
    main()
