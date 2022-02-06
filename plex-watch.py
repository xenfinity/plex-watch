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
  
  def get_account_from_creds(self, cred_file, key_file):
    username, password = self.decrypt_credentials(cred_file, key_file)
    return MyPlexAccount(username, password)

  def decrypt_credentials(self, cred_file, key_file):
    key = ''
 
    with open(key_file,'r') as key_in:
        key = key_in.read().encode()
    
    f = Fernet(key)
    with open(cred_file,'r') as cred_in:
        lines = cred_in.readlines()
        config = {}
        for line in lines:
            tuples = line.rstrip('\n').split('=',1)
            if tuples[0] in ('Username','Password'):
                config[tuples[0]] = tuples[1]
    
        username = config['Username']
        password = f.decrypt(config['Password'].encode()).decode()
        return [username, password]

class ConfigFileBuilder:

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

  data = None
  
  def parse_json(self, server_info):
    json_string = None
    with open(server_info) as json_file:
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

  def __init__(self, server):
    self.server = server
    self.sections = None
    self.shows = {}
    self.movies = {}

  def store_titles(self, titles):
    lib_name, lib_type, titles = titles
    if lib_type == 'show':
      self.shows[lib_name] = titles
    elif lib_type == 'movie':
      self.movies[lib_name] = titles

  def store_sections(self, sections):
    self.sections = sections


class ServerReader:

  def __init__(self, server):
    self.server = server

  def get_sections(self):
    print(self.server)
    sections = self.server.library.sections()
    return list(map((lambda x: x.title), sections))

  def get_titles(self, lib_name):
    lib = self.server.library.section(lib_name)
    lib_type = lib.type
    titles = set(list(map((lambda x: x.title), lib.search())))
    return [lib_name, lib_type, titles]
  
  def find_watched_status(self, titles):
    lib_name, lib_type, titles = titles
    num_of_titles = len(titles)
    server_name = self.server.friendlyName
    status = {}
    display = Display()

    if lib_type == 'show':
      for index, show_name in enumerate(titles):
        display.screen(f'Reading {server_name} ({index + 1}/{num_of_titles})...{show_name}'.ljust(100))
        show = self.server.library.section(lib_name).get(show_name)
        for ep in show.episodes():
            key = f'{show_name}<->{ep.seasonNumber}<->{ep.episodeNumber}'
            status[key] = ep.isWatched
      return status

    if lib_type == 'movie':
      for index, mov_name in enumerate(titles):
        display.screen(f'Reading {server_name} ({index + 1}/{num_of_titles})...{mov_name}'.ljust(100))
        movie = self.server.library.section(lib_name).get(mov_name)
        status[mov_name] = movie.isWatched
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
    
# TV_1 = conn_1.library.section('TV Shows')
# TV_2 = conn_2.library.section('TV Shows')

# Movies_1 = conn_1.library.section('Movies')
# Movies_2 = conn_2.library.section('Movies')


	


# shows_1 = list(map((lambda x: x.title), TV_1.search()))
# shows_2 = list(map((lambda x: x.title), TV_2.search()))

# dic_1 = build_show_dic(shows_1)
# dic_2 = build_show_dic(shows_2)

# show_set_1 = set(dic_1.keys())
# show_set_2 = set(dic_2.keys())

# difference = show_set_1.symmetric_difference(show_set_2)
# diff_1 = []
# diff_2 = []

# logging.info(f'{conn_1.friendlyName} Shows - {len(shows_1)}')
# for show in dic_1:
#     break
#     logging.info(f'\t{dic_1[show]}')
	
# logging.info(f'{conn_2.friendlyName} Shows - {len(shows_2)}')
# for show in dic_2:
#     break
#     logging.info(f'\t{dic_2[show]}')
	

# for show in difference:
#     if show in dic_1:
#         diff_1.append(dic_1[show])
#     else:
#         diff_2.append(dic_2[show])

# diff_1.sort()
# diff_2.sort()

# logging.info(f'{conn_1.friendlyName}')
# for title in diff_1:
#     logging.info(f'    {title}')
		
# logging.info(f'{conn_2.friendlyName}')
# for title in diff_2:
#     logging.info(f'    {title}')

# common_shows = show_set_1 & show_set_2
# common_shows = sorted(common_shows)
# num_of_shows = len(common_shows)

# watched_1 = find_watched_status(common_shows, conn_1, dic_1)
# print(reading_done(conn_1, common_shows))
# watched_2 = find_watched_status(common_shows, conn_2, dic_2)
# print(reading_done(conn_2, common_shows))

# def screen(message, title, num=none, den=none, ):
#     output = f'{message} ({index}/{num_eps})...{title}'.ljust(100)
#     print(output , end='\r')

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

class FileProcessor:
  def __init__(self):
    None
  

  

def main():
  cred_file = 'plex-creds.ini'
  key_file = 'plex-creds.key'
  json_file = 'server-info.json'

  file_builder = ConfigFileBuilder()

  if not path.exists(cred_file) or not path.exists(key_file):
    file_builder.build_credentials(cred_file, key_file)

  acct_factory = PlexAccountFactory()
  account = acct_factory.get_account_from_creds(cred_file, key_file)
  
  if not path.exists(json_file):
    file_builder.build_json(json_file, account)
    
  parser = MetadataParser()
  parser.parse_json(json_file)
  server_names = parser.get_server_names()

  srvr_factory = ServerFactory()
  servers = {}

  for name in server_names:
    servers[name] = srvr_factory.get_conn_from_name(account, name)

  for name, server in servers.items():
    data = ServerData(server)
    reader = ServerReader(server)

    data.store_sections(reader.get_sections())

    for section in data.sections:
      data.store_titles(reader.get_titles(section))



  # print(f'Synchronizing watched status ({num_eps}/{num_eps})...Done!'.ljust(100))
  # print('Synchronization complete!')

  

if __name__ == "__main__":
	main()
				


