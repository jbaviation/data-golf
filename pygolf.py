import configparser
import requests
import pandas as pd
import numpy as np

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

    def __connect_api(self, endpoint_name, params, prefix=None):
        """
        Connect to the api.
        """
        # Determine prefix
        prefix = '' if prefix is None else prefix.strip('/') + '/'

        # Define url
        url = self.base_url + prefix + endpoint_name

        # Perform GET request
        r = requests.get(url, params)

        # Transform request into DataFrame
        if int(r.status_code) == 200:
            return pd.DataFrame(r.json())
        else:
            print(f'Unable to read {url}, status code = {r.status_code}')
            return None  

    @staticmethod
    def _parse_name(players, column, drop_column=True):
        """
        Splits common full name into first name, last name, and suffix.

        Parameters
        ----------
        players : pd.DataFrame
            DataFrame that has a name column in the proper format for parsing.
        column : str
            Name of column that contains player names.
        drop_column : bool, default=True
            Whether or not to drop the column that contains the name that's been parsed.

        Returns
        -------
        pd.DataFrame
            Full DataFrame with name column parsed into 3 new columns:
                - 'first_name'
                - 'last_name'
                - 'suffix'
        """
        new_cols = ['last_name', 'suffix', 'first_name']

        # Extract pattern for name
        pat = r'^([^,]+),\s+([A-Za-z.]*,)?([^,]*)$'
        players[new_cols] = players[column].str.extract(pat)

        # Clean up columns
        for col in new_cols:
            players[col] = players[col].fillna('').str.strip().str.replace(',','')

        # Drop player_name column
        if drop_column:
            players = players.drop(column, axis=1)

        return players     

    def get_player_list(self, explode_name=True):
        """
        Function to retrieve player list and IDs. Returns the list of players who have played on a "major tour" 
        since 2018, or are playing on a major tour this week. IDs, country, amateur status included.

        Parameters
        ----------
        explode_name : bool, default=True
            Expands name into first, last name and suffix.

        Returns
        -------
        pd.DataFrame with columns:
            - amateur: boolean, whether or not an amateur.
            - country: str, golfer's representing country.
            - country_code: str, golfer's representing country's id code.
            - dg_id: int, datagolf id.
            - player_name: golfer's name (if explode_name=False)
            - first_name: golfer's first name (if explode_name=True)
            - last_name: golfer's last name (if explode_name=True)
            - suffix: golfer's suffix (if explode_name=True)
        """

        # Call __connect_api function
        players = self.__connect_api(endpoint_name='get-player-list', 
                                     params={
                                        'key': self.api_key,
                                        'file_format': 'json'
                                     })

        # Expand name if desired
        if explode_name:
            players = self._parse_name(players, 'player_name', drop_column=True)

        return players

    def get_tour_schedules(self, tour='pga', explode_location=True):
        """
        Current season schedules for the primary tours (PGA, European, KFT). Includes event names/ids, 
        course names/ids, and location (city/country and latitude, longitude coordinates) data for select 
        tours.

        Parameters
        ----------
        tour : {'pga', 'euro', 'kft'}, default='pga'
            The tour which to retrieve the schedule.
        explode_location : bool, default=True
            If true; city, state, and country are attempted to be parsed from the location column. This
            has had limited testing and it is possible some locations don't parse properly.

        Returns
        -------
        pd.DataFrame with columns:
            - current_season: int, season which this data is pulled from.
            - tour: str, golf tour for this data
            - course: str, course name for this data
            - course_key: int, identifier for this course
            - event_id: int, identifier for the particular event
            - event_name: str, name of the tour event
            - latitude: float, latitude of the location of the event
            - longitude: float, longitude of the location of the event
            - start_date: str, date which the tournament started in '%Y-%m-%d' format
            - city: str, city where the event took place (optional)
            - state: str, state where the event took place (if applicable) (optional)
            - country: str, country where the event took place (optional)
            - location: str, full name of the location where the event took place
        """

        # Call __connect_api function
        schedule = self.__connect_api(endpoint_name='get-schedule', 
                                      params={
                                        'key': self.api_key,
                                        'file_format': 'json',
                                        'tour': tour
                                      })

        # Combine details
        course_deets = pd.json_normalize(schedule['schedule'])
        basic_deets = schedule.drop('schedule', axis=1)
        df = pd.concat([basic_deets, course_deets], axis=1)  # Combine frames
        
        if explode_location:
            # Find initial regex patterns
            df['city'] = df['location'].str.extract(r'^([^,]*)')
            df['us_state'] = df['location'].str.extract(r'\b([A-Z]{2})\b')
            df['other_state'] = df['location'].str.extract(r'^[^,]*,([^,]*),')
            df['country'] = df['location'].str.extract(r'([^,]*)$')

            # Strip unecessary white space
            for col in ['city', 'us_state', 'other_state', 'country']:
                df[col] = df[col].str.strip()

            # Cleanup country and state
            df['country'] = np.where(df['us_state']==df['country'], 'United States', df['country'])
            df['state'] = df['us_state'].fillna(df['other_state'])

            # Return all the necessary data
            cols = ['current_season', 'tour', 'course', 'course_key', 'event_id', 'event_name', 'latitude', 
                    'longitude', 'start_date', 'city', 'state', 'country', 'location']
        else:
            cols = ['current_season', 'tour', 'course', 'course_key', 'event_id', 'event_name', 'latitude', 
                    'longitude', 'start_date', 'location']
        return df[cols]
    
    def get_field_updates(self, tour='pga'):
        """
        Up-to-the-minute field updates on WDs, Monday Qualifiers, tee times, and fantasy salaries for PGA Tour, 
        European Tour, and Korn Ferry Tour events. Includes data golf IDs and tour-specific IDs for each player 
        in the field.

        Parameters
        ----------
        tour : {'pga', 'euro', 'kft'}, default='pga'
            The tour which to retrieve the schedule.

        Returns
        -------
        pd.DataFrame
            Columns vary depending on the event that is being retrieved.
        """
        # Call __connect_api function
        field = self.__connect_api(endpoint_name='field-updates', 
                                   params={
                                        'key': self.api_key,
                                        'file_format': 'json',
                                        'tour': tour
                                    })
        
        # Combine details
        course_deets = pd.json_normalize(field['field'])
        basic_deets = field.drop(['field', 'event_name'], axis=1)
        df = pd.concat([basic_deets, course_deets], axis=1)

        return df
    
    def get_dg_rankings(self, explode_name=True):
        """
        Returns the top 500 players in the current DG rankings, along with each player's skill estimate and 
        respective OWGR rank.

        Parameters
        ----------
        explode_name : bool, default=True
            Expands name into first, last name and suffix.

        Returns
        -------
        pd.DataFrame with columns:
            - last_updated: datetime, last datetime that this dataframe was updated
            - am: boolean, whether or not next tee time is am
            - country: str, golfer's representing country's id code.
            - datagolf_rank: int, datagolf.com's player ranking.
            - dg_id: int, datagolf id.
            - dg_skill_estimate: float, datagolf.com's skill ranking.
            - owgr_rank: int, official world golf ranking.
            - primary_tour: str, primary golf tour of the player.
            - player_name: golfer's name (if explode_name=False)
            - first_name: golfer's first name (if explode_name=True)
            - last_name: golfer's last name (if explode_name=True)
            - suffix: golfer's suffix (if explode_name=True)      
        """

        # Call __connect_api function
        rankings = self.__connect_api(endpoint_name='get-dg-rankings', 
                                      params={
                                        'key': self.api_key,
                                        'file_format': 'json'},
                                      prefix='preds'
                                     )
        
        # Combine details
        player_deets = pd.json_normalize(rankings['rankings'])
        basic_deets = rankings.drop(['rankings', 'notes'], axis=1)
        df = pd.concat([basic_deets, player_deets], axis=1)

        # Expand name if desired
        if explode_name:
            df = self._parse_name(df, 'player_name', drop_column=True)

        return df