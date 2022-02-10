from mimetypes import init
from plexapi.myplex import MyPlexAccount
from cryptography.fernet import Fernet
import ctypes
from enum import Enum
import os
import sys
import json
import time
from os import path
import logging
from datetime import datetime

# log_name = datetime.now().strftime('watch-sync_%Y-%m-%d_%H-%M')
# logging.basicConfig(filename=f'{log_name}.log', encoding='utf-8', level=logging.INFO)


class Display:

    def message(self, message):
        print(message.ljust(150))

    def screen(self, message):
        print(message.ljust(150), end='\r')


class Section(Enum):

    SHOW = 'show'
    MOVIE = 'movie'
    SHOWS = 'shows'
    MOVIES = 'movies'
    EPISODES = 'episodes'


# taken from https://www.geeksforgeeks.org/create-a-credential-file-using-python/
class Credentials():

    def __init__(self, cred_file, key_file):
        self.__username = ""
        self.__key = ""
        self.__password = ""
        self.__cred_file = cred_file
        self.__key_file = key_file
        self.__time_of_exp = -1

    @property
    def username(self):
        return self.__username

    @username.setter
    def username(self, username):
        while (username == ''):
            username = input(
                'Enter a proper User name, blank is not accepted:')
        self.__username = username

    @property
    def password(self):
        return self.__password

    @password.setter
    def password(self, password):
        self.__key = Fernet.generate_key()
        f = Fernet(self.__key)
        self.__password = f.encrypt(password.encode()).decode()
        del f

    @property
    def expiry_time(self):
        return self.__time_of_exp

    @expiry_time.setter
    def expiry_time(self, exp_time):
        if(exp_time >= 2):
            self.__time_of_exp = exp_time

    def create_cred(self):
        """
        This function is responsible for encrypting the password and create key file for
        storing the key and create a credential file with user name and password
        """

        cred_filename = self.__cred_file

        with open(cred_filename, 'w') as file_in:
            file_in.write("#Credential file:\nUsername={}\nPassword={}\nExpiry={}\n"
                          .format(self.__username, self.__password, self.__time_of_exp))
            file_in.write("++"*20)

        if(os.path.exists(self.__key_file)):
            os.remove(self.__key_file)

        try:
            os_type = sys.platform
            if (os_type == 'linux'):
                self.__key_file = '.' + self.__key_file

            with open(self.__key_file, 'w') as key_in:
                key_in.write(self.__key.decode())

                if(os_type == 'win32'):
                    ctypes.windll.kernel32.SetFileAttributesW(
                        self.__key_file, 2)
                else:
                    pass

        except PermissionError:
            os.remove(self.__key_file)
            print("A Permission error occurred.\n Please re run the script")
            sys.exit()

        self.__username = ""
        self.__password = ""
        self.__key = ""
        self.__key_file


class PlexAccountFactory:

    def __init__(self, cred_file, key_file):
        self.cred_file = cred_file
        self.key_file = key_file

    def get_account_from_creds(self):
        username, password = self.decrypt_credentials()
        return MyPlexAccount(username, password)

    def decrypt_credentials(self):
        key = ''

        with open(self.key_file, 'r') as key_in:
            key = key_in.read().encode()

        f = Fernet(key)
        with open(self.cred_file, 'r') as cred_in:
            lines = cred_in.readlines()
            config = {}
            for line in lines:
                tuples = line.rstrip('\n').split('=', 1)
                if tuples[0] in ('Username', 'Password'):
                    config[tuples[0]] = tuples[1]

            username = config['Username']
            password = f.decrypt(config['Password'].encode()).decode()
            return [username, password]


class FileBuilder:

    def build_credentials(self, cred_file_name, key_file_name):
        creds = Credentials(cred_file_name, key_file_name)

        creds.username = input("Enter Plex Email:")
        creds.password = input("Enter Plex Password:")

        creds.create_cred()

  # def build_json(self, json_file, account):
  #   config = Configuration(json_file, account)


class MetadataParser:

    def __init__(self, json_file_name):
        self.data = None
        self.json_file_name = json_file_name

    def parse_json(self):
        json_string = None
        with open(self.json_file_name) as json_file:
            json_string = json.load(json_file)
        self.data = json_string['servers']

    def get_server_names(self):
        server_names = []
        for server in self.data:
            server_names.append(server['name'])
        return server_names

# SHOWLIST = [
#   {
#     'title' : 'A.P. Bio',
#     'episodes' : {


#     },
#   }
#   ]
# MOVIELIST = ['A.P. Bio', 'Made for Love', 'You', 'Good Eats']

# class Episode:
#     def __init__(self, episode):
#         self.episode = episode

# class Library:
#     def __init__(self):
#         self.friendlyName = 'test_library'
#         self.library = []

#     def section(self, sec_name):
#         if sec_name == 'TV Shows':
#             return self.build_library(SHOWLIST)

#     def build_library(self, show_list):
#       for show in show_list:
#           episode = Episode(show)
#           self.library.append(episode)
#       return self.library

# class PlexServer:

#     def __init__(self, account, name):
#         self.account = account
#         self.friendlyName = name
#         self.library = Library()

class ServerFactory:

    def get_conn_from_name(self, account, name):
        return account.resource(name).connect()

    # def get_test_conn(self, account, name):
    #     return PlexServer(account, name)


class ServerData:

    def __init__(self, server, reader):
        self.server = server
        self.reader = reader
        self.shows = {}
        self.movies = {}

        self.sections = reader.get_sections()
        self.store_titles()

    def store_titles(self):
        for section in self.sections:
            lib_name, lib_type, titles = self.reader.get_titles(section)
            if lib_type == Section.SHOW.value:
                self.shows[lib_name] = titles
            elif lib_type == Section.MOVIE.value:
                self.movies[lib_name] = titles


class ServerReader:

    def __init__(self, server):
        self.server = server
        self.server_name = server.friendlyName
        self.show_sections = []
        self.movie_sections = []
        self.set_sections_by_type()

    def get_sections(self):
        sections = self.server.library.sections()
        return list(map((lambda x: x.title), sections))

    def set_sections_by_type(self):
        sections = self.get_sections()
        for name in sections:
            if self.server.library.section(name).type == Section.SHOW.value:
                self.show_sections.append(name)
            elif self.server.library.section(name).type == Section.MOVIE.value:
                self.movie_sections.append(name)

    def get_titles(self, lib_name):
        lib = self.server.library.section(lib_name)
        lib_type = lib.type
        titles = set(list(map((lambda x: x.title), lib.search())))
        return [lib_name, lib_type, titles]

    def get_status(self, titles, lib_name):
        num_of_titles = len(titles)
        server_name = self.server.friendlyName

        lib_type = self.server.library.section(lib_name).type
        status = {}
        display = Display()

        for index, title in enumerate(titles):
            display.screen(
                f'Reading {lib_type}s in {lib_name} on {server_name} ({index + 1}/{num_of_titles})...{title}')
            title_object = self.server.library.section(lib_name).get(title)

            if lib_type == Section.SHOW.value:
                for ep in title_object.episodes():
                    key = f'{title}<->{ep.seasonNumber}<->{ep.episodeNumber}'
                    status[key] = ep.isWatched
            elif lib_type == Section.MOVIE.value:
                status[title] = title_object.isWatched

        display.message(
            f'Reading {lib_type}s in {lib_name} on {server_name} ({num_of_titles}/{num_of_titles})...Done!')
        return status

    def get_movies(self, movie_name):
        movies = []
        for lib_name in self.movie_sections:
            try:
                movie = self.server.library.section(lib_name).get(movie_name)
                movies.append(movie)
            except:
                print(f"{movie_name} not found in {lib_name} on {self.server_name}")
                continue
        return movies

    def get_episodes(self, key):
        episodes = []
        show_name, sNum, eNum = key.split('<->')
        for lib_name in self.show_sections:
            try:
                episode = self.server.library.section(lib_name) \
                    .get(show_name) \
                    .episode(season=sNum, episode=eNum)
                episodes.append(episode)
            except:
                print(f"{key} not found in {lib_name} on {self.server_name}")
                continue
        return episodes


class Processor:

    def __init__(self, server_attr):
        self.server_attr = server_attr
        self.all_shows = {}
        self.all_movies = {}
        self.all_episodes = {}
        self.common_shows = {}
        self.common_movies = {}
        self.common_episodes = {}
        self.difference_shows = {}
        self.difference_movies = {}
        self.difference_episodes = {}
        self.status = {}
        self.to_be_marked = {
            Section.EPISODES.value: [],
            Section.MOVIES.value: []
        }

        self.cache_all_titles()
        self.set_common(Section.SHOWS.value)
        self.set_common(Section.MOVIES.value)
        self.set_difference(Section.SHOWS.value)
        self.set_difference(Section.MOVIES.value)

        self.set_watched_status()

        self.cache_all_episodes()
        self.set_common(Section.EPISODES.value)
        self.set_difference(Section.EPISODES.value)

        self.find_titles_to_mark()
        self.mark_watched()

    def cache_all_titles(self):

        for server_name, attr in self.server_attr.items():
            data = attr['data']
            shows = set()
            movies = set()
            for lib_name, titles in data.shows.items():
                shows = shows.union(titles)
            for lib_name, titles in data.movies.items():
                movies = movies.union(titles)
            self.all_shows[server_name] = shows
            self.all_movies[server_name] = movies

    def set_common(self, name):

        match name:
            case Section.SHOWS.value:
                self.common_shows = set.intersection(
                    *list(self.all_shows.values()))
            case Section.MOVIES.value:
                self.common_movies = set.intersection(
                    *list(self.all_movies.values()))
            case Section.EPISODES.value:
                self.common_episodes = set.intersection(
                    *list(self.all_episodes.values()))

    def set_difference(self, name):

        match name:
            case Section.SHOWS.value:
                for server_name, shows in self.all_shows.items():
                    difference = shows.symmetric_difference(self.common_shows)
                    for show in difference:
                        if show in self.difference_shows:
                            self.difference_shows[show].append(server_name)
                        else:
                            self.difference_shows[show] = [server_name]

            case Section.MOVIES.value:
                for server_name, movies in self.all_movies.items():
                    difference = movies.symmetric_difference(
                        self.common_movies)
                    for movie in difference:
                        if movie in self.difference_movies:
                            self.difference_movies[movie].append(server_name)
                        else:
                            self.difference_movies[movie] = [server_name]

            case Section.EPISODES.value:
                for server_name, episodes in self.all_episodes.items():
                    difference = episodes.symmetric_difference(
                        self.common_episodes)
                    for episode in difference:
                        if episode in self.difference_episodes:
                            self.difference_episodes[episode].append(
                                server_name)
                        else:
                            self.difference_episodes[episode] = [server_name]

    def set_watched_status(self):

        for server_name, attr in self.server_attr.items():
            data = attr['data']
            reader = attr['reader']
            ep_status = {}
            movie_status = {}

            for lib_name, titles in data.shows.items():
                common_titles_in_lib = titles.intersection(
                    self.common_shows)
                show_statuses = reader.get_status(
                    common_titles_in_lib, lib_name)
                ep_status.update(show_statuses)

            for lib_name, titles in data.movies.items():
                common_titles_in_lib = titles.intersection(
                    self.common_movies)
                movie_statuses = reader.get_status(
                    common_titles_in_lib, lib_name)
                movie_status.update(movie_statuses)

            self.status[server_name] = {
                Section.EPISODES.value: ep_status, Section.MOVIES.value: movie_status}

    def cache_all_episodes(self):

        for server_name, status_data in self.status.items():
            data_to_set = set(status_data[Section.EPISODES.value].keys())
            self.all_episodes[server_name] = data_to_set

    def find_titles_to_mark(self):
        episodes = self.common_episodes
        movies = self.common_movies

        for episode in episodes:
            watched_arr = []
            for server_name, status_data in self.status.items():
                if episode in status_data[Section.EPISODES.value]:
                    watched_arr.append(
                        status_data[Section.EPISODES.value][episode])
            if any(watched_arr) and not all(watched_arr):
                self.to_be_marked[Section.EPISODES.value].append(episode)

        for movie in movies:
            watched_arr = []
            for server_name, status_data in self.status.items():
                if movie in status_data[Section.MOVIES.value]:
                    watched_arr.append(
                        status_data[Section.MOVIES.value][movie])
            if any(watched_arr) and not all(watched_arr):
                self.to_be_marked[Section.MOVIES.value].append(movie)

    def mark_watched(self):

        episodes_to_mark = self.to_be_marked[Section.EPISODES.value]
        movies_to_mark = self.to_be_marked[Section.MOVIES.value]
        for server_name, attr in self.server_attr.items():
            reader = attr['reader']
            for episode in episodes_to_mark:
                episodes_on_server = reader.get_episodes(episode)
                for ep in episodes_on_server:
                    ep.markWatched()

            for movie in movies_to_mark:
                movies_on_server = reader.get_movies(movie)
                for mov in movies_on_server:
                    mov.markWatched()


def main():
    cred_file_name = 'plex-creds.ini'
    key_file_name = 'plex-creds.key'
    json_file_name = 'server-info.json'

    file_builder = FileBuilder()
    display = Display()

    if not path.exists(cred_file_name) or not path.exists(key_file_name):
        file_builder.build_credentials(cred_file_name, key_file_name)

    display.screen(f'Retrieving Plex account...')
    acct_factory = PlexAccountFactory(cred_file_name, key_file_name)
    account = acct_factory.get_account_from_creds()
    display.message(f'Retrieving Plex account...Done!')

    if not path.exists(json_file_name):
        file_builder.build_json(json_file_name, account)

    parser = MetadataParser(json_file_name)
    parser.parse_json()
    server_names = parser.get_server_names()

    server_factory = ServerFactory()
    servers = {}
    server_attr = {}

    display.screen(f'Connecting to servers...')
    for name in server_names:
        servers[name] = server_factory.get_conn_from_name(account, name)
    display.message(f'Connecting to servers...Done!')

    for name, server in servers.items():
        reader = ServerReader(server)
        data = ServerData(server, reader)

        server_attr[name] = {
            'server': server,
            'data': data,
            'reader': reader,
        }

    process = Processor(server_attr)

    print('Synchronization complete!')
    print(process.difference_shows)
    print(process.difference_movies)
    print(process.difference_episodes)


if __name__ == "__main__":
    main()
