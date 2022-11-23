import argparse
import email
import email.message
import getpass
import json
import os
import re
import socket
from typing import NoReturn
import glosocket
import TP4_utils


class Client:

    def __init__(self, destination: str) -> None:
        """
        Cette méthode est automatiquement appelée à l’instanciation du client,
        elle doit :
        - Initialiser le socket du client et le connecter à l’adresse en paramètre.
        - Préparer un attribut « _logged_in » pour garder en mémoire l’état de
            l’authentification avec le serveur.
        - Préparer un attribut « _username » pour garder en mémoire le nom 
            d’utilisateur utilisé pour l’authentification.

        Attention : ne changez pas le nom des attributs fournis, ils sont utilisés dans les tests. 
        Vous pouvez cependant ajouter des attributs supplémentaires.
        """
        self._logged_in = False
        self._username = ""

        try:
            socket_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socket_client.connect((destination, TP4_utils.SOCKET_PORT))
        except Exception:
            print("error in __init__()")
            exit()
        self._socket = socket_client

    def _recv_data(self) -> TP4_utils.GLO_message:
        """
        Cette fonction utilise le module glosocket pour récupérer un message.
        Elle doit être appelée systématiquement pour recevoir des données du serveur.

        Le message attendu est une chaine de caractère représentant un GLO_message 
        valide, qui est décodé avec le module json. Si le JSON est invalide 
        ou le résultat est None, le programme termine avec un code -1.
        """
        # TODO
        message = glosocket.recv_msg(self._socket)
        if message is None :
            print("error in _recv_data() : message is None")
            exit()
        return TP4_utils.GLO_message(json.loads(message))

    def _authentication(self) -> None:
        """
        Cette fonction traite l’authentification du client.

        La fonction, dans l’ordre :
        - Demande au client s’il souhaite se connecter ou créer un compte
        - Demande le nom d’utilisateur
        - Demande le mot de passe
        - Transmet la requête au serveur
        - Traite la réponse du serveur
        """

        choice = input(TP4_utils.CLIENT_AUTH_CHOICE)
        if choice == "1" or choice == "2" :

            username = input("Entrez votre nom d'utilisateur :")
            if username is None :
                print("Nom d'utilisateur invalide")
                return

            password = input("Entrez votre mot de passe :")
            if password is None :
                print("Mot de passe pas assez robuste")
                return

            authType = TP4_utils.message_header.AUTH_LOGIN
            if choice == "1" :
                authType = TP4_utils.message_header.AUTH_REGISTER

            message = json.dumps({
                "header": authType,
                "data": {"username": username, "password": password}
            })
            glosocket.send_msg(self._socket, TP4_utils.GLO_message(message))
            response = self._recv_data()

            if response.header == TP4_utils.message_header.OK :
                self._logged_in = True
                self._username = username
            else :
                print("Mauvais nom d'utilisateur ou mot de passe")
            
            

    def _main_loop(self) -> None:
        """
        Cette fonction traite les actions du client après authentification.

        La fonction affiche le menu principal à l’utilisateur, récupère son
        choix et appelle l’une des fonctions _reading, _sending ou _get_stats
        ou quitte avec un code 0.
        """
        choice = input(TP4_utils.CLIENT_USE_CHOICE)
    
        if choice == "1" :
            self._reading()
        
        if choice == "2" :
            self._sending()
        
        if choice == "3" :
            self._get_stats()

        if choice == "4" :
            exit()


    def _reading(self) -> None:
        """
        Cette fonction traite les requêtes de consultation de courriel.

        La fonction, dans l’ordre :
        - Envoie une requête au serveur de consultation de courriel.
        - Récupère la liste des sujets depuis le serveur.
        - Demande à l’utilisateur quel courriel consulter.
        - Transmet ce choix au serveur.
        - Récupère le courriel choisi depuis le serveur.
        - Affiche le courriel dans le terminal avec le gabarit EMAIL_DISPLAY.
        """
        # TODO
        message = json.dumps({
                "header": TP4_utils.message_header.INBOX_READING_REQUEST,
                "data": self._username
            })
        glosocket.send_msg(self._socket, TP4_utils.GLO_message(message))

        response1 = self._recv_data()
        if response1.header == TP4_utils.message_header.ERROR or response1.data is None :
            return;

        for email in response1.data :
            print(TP4_utils.SUBJECT_DISPLAY.format(email.number, email.subject, email.source))
        choice = input(TP4_utils.CLIENT_USE_CHOICE)

        message = json.dumps({
                "header": TP4_utils.message_header.INBOX_READING_CHOICE,
                "data": {"username": self._username, "password": choice}
            })
        glosocket.send_msg(self._socket, TP4_utils.GLO_message(message))

        response2 = self._recv_data()
        if response2.header == TP4_utils.message_header.OK :
            print(TP4_utils.EMAIL_DISPLAY.format(response2.data["source"], response2.data["destination"], response2.data["subject"], response2.data["content"]))
        else :
            print(response2.data)
        

    def _sending(self) -> None:
        """
        Cette fonction traite les requêtes d’envoi de courriel.

        Cette fonction, dans l’ordre :
        - Demande l’adresse email de destination
        - Demande le sujet
        - Demande le contenu du message.
        - Avec ces informations, crée un objet EmailMessage
        - Envoie l’objet sous forme de chaine de caractère au serveur
        - Récupère la réponse du serveur, affiche l’erreur si nécessaire

        Note : un utilisateur termine la saisie avec un point sur une
        ligne
        """
        # TODO
        courriel = email.message.EmailMessage()
        courriel["From"] = f"{self._username}@{TP4_utils.SERVER_DOMAIN}"
        courriel["To"] = input("Entrer l'adresse courriel du destinataire : ")
        courriel["Subject"] = input("Entrer le sujet du courriel : ")
        emailContent = ""
        print("Entrer le contenu du courriel puis terminer le en entrant un point seul : ")
        while (True) :
            txt = input("Entrer le contenu du courriel : ")
            if txt == "." :
                break
            emailContent += txt + os.linesep
        
        courriel.set_content(emailContent)

        message = json.dumps({
                "header": TP4_utils.message_header.EMAIL_SENDING,
                "data": courriel.as_string()
            })
        glosocket.send_msg(self._socket, TP4_utils.GLO_message(message))

        response = self._recv_data()
        if response.header == TP4_utils.message_header.ERROR :
            print(response.data)
            
        

    def _get_stats(self) -> None:
        """
        Cette fonction traite les requêtes de demandes de statistiques.

        Cette fonction, dans l’ordre :
        - Envoie une requête de statistique au serveur.
        - Récupère les statistiques depuis le serveur.
        - Affiche les statistiques dans le terminal avec le gabarit 
            STATS_DISPLAY.
        """
        # TODO
        message = json.dumps({
                "header": TP4_utils.message_header.STATS_REQUEST,
                "data": self._username
            })
        glosocket.send_msg(self._socket, TP4_utils.GLO_message(message))

        response = self._recv_data()
        if response.header == TP4_utils.message_header.OK :
            print(TP4_utils.STATS_DISPLAY.format(response.data["count"], response.data["size"]))
        else :
            print(response.data)


    def run(self) -> NoReturn:
        """
        Appelle la fonction _athentication en boucle jusqu’à la connexion.
        Une fois connecté, appelle la fonction _main_loop en boucle jusqu’à
        la fin du programme.
        """
        while not self._logged_in:
            self._authentication()
        while True:
            self._main_loop()


def main() -> NoReturn:
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--destination",
                        dest="destination",  type=str, action="store", required=True)
    destination = parser.parse_args().destination
    Client(destination).run()


if __name__ == '__main__':
    main()
