import configparser
import requests
import pandas as pd

class datagolf:
    """
    Class which is meant to interact with the datagolf API for use in retrieving desired information without
    requiring requests. 'config.ini' file must be present and up-to-date in this directory.
    """

    def __init__(self):
        self.api_key = self.get_api_key()  # Set api key
        self.base_url = 'https://feeds.datagolf.com/'  # Set base url for each endpoint

    def get_api_key(self):
        """
        Read the api key from the config.ini file.
        """

        # Read the config file
        cp = configparser.ConfigParser()
        cp.read('config.ini')

        return cp['DEFAULT']['api_key']

    def test_config_file(self):
        """
        This function tests the config.ini file to confirm all elements are entered correctly.
        """
        pass  # TODO

    def connect_api(self):
        """
        Connect to the api.
        """
        # Generate parameters
        pass

    def get_player_list(self):
        """Function to retrieve player list and IDs. Returns the list of players who have played on a "major tour" 
        since 2018, or are playing on a major tour this week. IDs, country, amateur status included.

        Returns
        -------
        pd.DataFrame with columns:
            - amateur: boolean, whether or not an amateur.
            - country: str, golfer's representing country.
            - country_code: str, golfer's representing country's id code.
            - dg_id: int, datagolf id.
            - player_name: golfer's name.
        """

        # Define url
        player_list_enpdoint_name = 'get-player-list'
        url = self.base_url + player_list_enpdoint_name

        # Setup params for request
        params = {
            'key': self.api_key,
            'file_format': 'json'
        }

        # Perform GET request
        r = requests.get(url, params)

        # Transform request into DataFrame
        if int(r.status_code) == 200:
            return pd.DataFrame(r.json())
        else:
            print(f'Unable to read Player List, status code = {r.status_code}')
            return None
        


