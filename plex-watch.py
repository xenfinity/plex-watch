from plexapi.myplex import MyPlexAccount
from cryptography.fernet import Fernet
import ctypes
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

  def print_message(self, message):
    print(message)
  
  def screen(self, message):
    print(message, end='\r')
    
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
	def username(self,username):
		while (username == ''):
			username = input('Enter a proper User name, blank is not accepted:')
		self.__username = username

	@property
	def password(self):
		return self.__password

	@password.setter
	def password(self,password):
		self.__key = Fernet.generate_key()
		f = Fernet(self.__key)
		self.__password = f.encrypt(password.encode()).decode()
		del f

	@property
	def expiry_time(self):
		return self.__time_of_exp

	@expiry_time.setter
	def expiry_time(self,exp_time):
		if(exp_time >= 2):
			self.__time_of_exp = exp_time


	def create_cred(self):
		"""
		This function is responsible for encrypting the password and create key file for
		storing the key and create a credential file with user name and password
		"""

		cred_filename = self.__cred_file

		with open(cred_filename,'w') as file_in:
			file_in.write("#Credential file:\nUsername={}\nPassword={}\nExpiry={}\n"
			.format(self.__username,self.__password,self.__time_of_exp))
			file_in.write("++"*20)

		if(os.path.exists(self.__key_file)):
			os.remove(self.__key_file)

		try:
			os_type = sys.platform
			if (os_type == 'linux'):
				self.__key_file = '.' + self.__key_file

			with open(self.__key_file,'w') as key_in:
				key_in.write(self.__key.decode())

				if(os_type == 'win32'):
					ctypes.windll.kernel32.SetFileAttributesW(self.__key_file, 2)
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

class Configuration:

  def __init__(self, json_file, account):
    self.json_file = json_file

class PlexAccountFactory:

  def __init__(self, cred_file, key_file):
      self.cred_file = cred_file
      self.key_file = key_file
  
  def get_account_from_creds(self):
    username, password = self.decrypt_credentials()
    return MyPlexAccount(username, password)

  def decrypt_credentials(self):
    key = ''
 
    with open(self.key_file,'r') as key_in:
        key = key_in.read().encode()
    
    f = Fernet(key)
    with open(self.cred_file,'r') as cred_in:
        lines = cred_in.readlines()
        config = {}
        for line in lines:
            tuples = line.rstrip('\n').split('=',1)
            if tuples[0] in ('Username','Password'):
                config[tuples[0]] = tuples[1]
    
        username = config['Username']
        password = f.decrypt(config['Password'].encode()).decode()
        return [username, password]

class FileBuilder:

  def build_credentials(self, cred_file, key_file):
    creds = Credentials(cred_file, key_file)

    creds.username = input("Enter UserName:")
    creds.password = input("Enter Password:")

    creds.create_cred()
    print("Credential files created successfully at {}"
    .format(time.ctime()))

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

class ServerFactory:

  def get_conn_from_name(self, account, name):
    return account.resource(name).connect()

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
      if lib_type == 'show':
        self.shows[lib_name] = titles
      elif lib_type == 'movie':
        self.movies[lib_name] = titles

class ServerReader:

  def __init__(self, server):
    self.server = server

  def get_sections(self):
    sections = self.server.library.sections()
    return list(map((lambda x: x.title), sections))

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
      display.screen(f'Reading shows on {server_name} ({index + 1}/{num_of_titles})...{title}'.ljust(100))
      title_object = self.server.library.section(lib_name).get(title)

      if lib_type == 'show':
        for ep in title_object.episodes():
            key = f'{title}<->{ep.seasonNumber}<->{ep.episodeNumber}'
            status[key] = ep.isWatched
      elif lib_type == 'movie':
        status[title] = title_object.isWatched
    return status

  def get_mov(self, key):
    for lib in self.shows:
      try:
        movie = self.server.library.section(lib).get(key)
        return movie
      except:
        print("movie not found")
        continue

  def get_ep(self, key):
    show, sNum, eNum = key.split('<->')
    for lib in self.shows:
      try:
        episode = self.server.library.section(lib).get(show).episode(season=sNum, episode=eNum)
        return episode
      except:
        print("episode not found")
        continue
  
  def reading_done(self, titles):
    num_of_titles = len(titles)
    return f'Reading {self.server.friendlyName} ({num_of_titles}/{num_of_titles})...Done!'.ljust(100)



class Processor:
  
  def __init__(self, server_attr):
    self.server_attr = server_attr
    self.all_shows = []
    self.all_movies = []
    self.status = {}
    self.to_be_marked = {}

    self.cache_all_titles()
    self.set_common()
    self.set_difference()
    self.set_watched_status()
    # self.find_titles_to_mark()
    # self.mark_watched()

  def cache_all_titles(self):

    for server_name, attr in self.server_attr.items():
      print(server_name)
      data = attr['data']
      shows = set()
      movies = set()
      for lib_name, titles in data.shows.items():
        shows = shows.union(titles)
      for lib_name, titles in data.movies.items():
        movies = movies.union(titles)
      self.all_shows.append(shows)
      self.all_movies.append(movies)

  def set_common(self):

    self.common = {
      'shows' : set.intersection(*self.all_shows),
      'movies' : set.intersection(*self.all_movies)
    }
      
  def set_difference(self):
    
    self.difference = {
      'shows' : set.symmetric_difference(*self.all_shows),
      'movies' : set.symmetric_difference(*self.all_movies)
    }
  
  def set_watched_status(self):
    for server_name, attr in self.server_attr.items():
      data = attr['data']
      reader = attr['reader']
      ep_status = {}
      movie_status = {}
      
      for lib_name, titles in data.shows.items():
        common_titles_in_lib = titles.intersection(self.common['shows'])
        show_statuses = reader.get_status(common_titles_in_lib, lib_name)
        ep_status.update(show_statuses)
        
      for lib_name, titles in data.movies.items():
        common_titles_in_lib = titles.intersection(self.common['movies'])
        movie_statuses = reader.get_status(common_titles_in_lib, lib_name)
        movie_status.update(movie_statuses)

      self.status[server_name] = {'episodes' : ep_status, 'movies' : movie_status}

  # def find_titles_to_modify(self):
  #   num_eps = len(watched_1)
  #   for episode, data in self.ep_status.items():
  #       show, sNum, eNum = episode.split('<->')
  #       screen('Synchronizing watched status', f'{show}-S{sNum}E{eNum}', index, num_eps )
  #       print(screen , end='\r') 
  #       if episode in watched_2:
  #           if watched_1[episode] != watched_2[episode]:
  #               if watched_1[episode]:
  #                   get_ep(episode, conn_2, dic_2).markWatched()
  #               else:
  #                   get_ep(episode, conn_1, dic_1).markWatched()
  
  # def mark_watched(self):
  #   None



def main():
  cred_file = 'plex-creds.ini'
  key_file = 'plex-creds.key'
  json_file_name = 'server-info.json'

  file_builder = FileBuilder()

  if not path.exists(cred_file) or not path.exists(key_file):
    file_builder.build_credentials(cred_file, key_file)

  acct_factory = PlexAccountFactory(cred_file, key_file)
  account = acct_factory.get_account_from_creds()
  
  if not path.exists(json_file_name):
    file_builder.build_json(json_file_name, account)
    
  parser = MetadataParser(json_file_name)
  parser.parse_json()
  server_names = parser.get_server_names()

  server_factory = ServerFactory()
  servers = {}
  server_attr = {}

  for name in server_names:
    servers[name] = server_factory.get_conn_from_name(account, name)

  for name, server in servers.items():   
    reader = ServerReader(server)
    data = ServerData(server, reader)

    server_attr[name] = {
      'server' : server,
      'data' : data,
      'reader' : reader
    }

  process = Processor(server_attr)
  
  print(process.status)


  # print(f'Synchronizing watched status ({num_eps}/{num_eps})...Done!'.ljust(100))
  # print('Synchronization complete!')

if __name__ == "__main__":
	main()
				

# num_eps = len(watched_1)
# for index, episode in enumerate(watched_1):
#     show, sNum, eNum = episode.split('<->')
#     screen('Synchronizing watched status', f'{dic_1[show]}-S{sNum}E{eNum}', index, num_eps )
#     print(screen , end='\r') 
#     if episode in watched_2:
#         if watched_1[episode] != watched_2[episode]:
#             if watched_1[episode]:
#                 get_ep(episode, conn_2, dic_2).markWatched()
#             else:
#                 get_ep(episode, conn_1, dic_1).markWatched()