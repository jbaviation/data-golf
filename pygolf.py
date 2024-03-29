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

    def __connect_api(self, endpoint_name, params, prefix=None, return_request=False):
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
        if (r is None) or (r.status_code != 200):
            base_msg = 'Issue occurred with the request for {}. Status code {} encountered.'
            msg = base_msg.format(endpoint_name, None) if r is None else base_msg.format(endpoint_name, r.status_code)
            raise DataGolfAPIResponseError(msg)
        
        # Consider if request is to be returned
        if return_request:
            return r
        else:
            return pd.DataFrame(r.json())

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
    
    def get_pre_tourney_predictions(self, add_position=None, tour='pga', odds_format='percent', event_id=None,
                                    year=None):
        """
        Get full-field probabilistic forecasts for upcoming tournaments.

        The forecasts for the upcoming tournaments include those for the PGA, European, and Korn Ferry Tour and
        from both datagolf baseline and baseline + course history & fit models. Probabilities provided for 
        various finish positions (make cut, top 20, top 5, win, etc).

        Parameters
        ----------
        add_position : list, optional
            List of additional positions to include in output. Defaults are win, top 5, top 10, top 20, 
            make cut. Options include [1, 2, 3 .... 48, 49, 50, 'top 30'].
            NOTE: The Datagolf API currently is unable to process these requests. This input is temporarily unavailable.
        tour : {'pga', 'euro', 'kft', 'opp', 'alt'}, default='pga'
            Specifies the tour.
        odds_format : {'percent', 'american', 'decimal', 'fraction'}, default='percent'
            Specifies the odds format.
        event_id : int, optional
            Unique event id (if specific event is requested). If no input is provided, the event defaults
            to the most current event. NOTE: additional API permissions may be required to perform this action.
        year : int {>=2020}, optional
            Specifies the calendar year (not season) of the event. If no input is provided, defaults to only
            the most current event. NOTE: additional API permissions may be required to perform this action.

        Returns
        -------
        pd.DataFrame with columns (NOTE: some columns vary based on the event)
            - event_name: str, name of the event
            - team_name | player_name: str, if team event; team_name is used...else player_name is used
            - dg_id: int, player datagolf id
            - country: str, golfer's representing country's id code
            - sample_size: int, UNKNOWN
            - last_updated: datetime, last datetime that this dataframe was updated
            - model: str, datagolf model used to make this prediction
            - make_cut: [type depends on 'odds_format' input], odds of making the cut
            - top_20 : [type depends on 'odds_format' input], odds of finishing top 20
            - top_10 : [type depends on 'odds_format' input], odds of finishing top 10
            - top_5 : [type depends on 'odds_format' input], odds of finishing top 5
            - win : [type depends on 'odds_format' input], odds of winning
            - {any selected 'add_position' values}
        """

        # Generate params input
        params = {
            'key': self.api_key,
            'file_format': 'csv',
            'odds_format': odds_format
        }

        # Add add_position in proper format
        if add_position is None: 
            pass  # don't do anything if optional input is not entered
        else:  # Temporary disallow any inputs into add_position
            raise DataGolfAPIInputError('add_position into get_pre_tourney_predictions is temporariily unavailable')
        # elif isinstance(add_position, (list, tuple)):
        #     add_position_str = [str(pos) for pos in add_position]
        #     params['add_position'] = ','.join(add_position_str)
        # else:
        #     raise DataGolfAPIInputError('Improper entry into get_pre_tourney_predictions add_position input')

        # Set endpoint and params (it can change depending on inputs)
        endpoint_name = 'pre-tournament-archive' if (event_id or year) else 'pre-tournament'
        if endpoint_name=='pre-tournament':
            params['tour'] = tour
        else:
            if event_id: params['event_id'] = str(event_id)
            if year: params['year'] = str(year)

        # Call __connect_api function
        predicts_req = self.__connect_api(endpoint_name=endpoint_name, 
                                          params=params, 
                                          prefix='preds',
                                          return_request=True
        )

        # The typical json request doesn't work with this dataset, convert csv string data into DataFrame
        csv_list = [row.split(',') for row in predicts_req.content.decode("utf-8").split('\n')]
        return pd.DataFrame(csv_list[1:], columns=csv_list[0])  # set first row as column header

    def get_player_decompositions(self, tour='pga', explode_name=True):
        """
        Returns a detailed breakdown of every player's strokes-gained prediction for upcoming tournaments.

        Parameters
        ----------
        tour : {'pga', 'euro', 'kft', 'opp', 'alt'}, default='pga'
            Specifies the tour.
        explode_name : bool, default=True
            Expands name into first, last name and suffix.

        Returns
        -------
        pd.DataFrame with columns
            - course_name : str, name of the course
            - event_name : str, name of the event
            - last_updated : datetime, last datetime that this dataframe was updated
            - age : int, age of the player during the event
            - age_adjustment : float, strokes gained adjustment for age
            - am : int, whether or not the player is an amateur
            - baseline_pred : float, TODO
            - cf_approach_comp : float, TODO
            - cf_short_comp : float, TODO
            - country: str, golfer's representing country's id code.
            - country_adjustment : TODO
            - course_experience_adjustment : float, strokes gained adjustment for course experience
            - course_history_adjustment : float, strokes gained adjustment for course history
            - dg_id : int, datagolf id
            - driving_accuracy_adjustment : float, strokes gained adjustment for driving accuracy
            - driving_distance_adjustment : float, strokes gained adjustment for driving distance
            - final_pred : float, total strokes gained prediction for this event? TODO
            - other_fit_adjustment : float, TODO
            - sample_size : int, TODO
            - std_deviation : float, TODO
            - strokes_gained_category_adjustment : float, TODO
            - timing_adjustment : float, TODO
            - total_course_history_adjustment : float, TODO
            - total_fit_adjustment : float, TODO
            - true_sg_adjustments : float, TODO
            - player_name: golfer's name (if explode_name=False)
            - first_name: golfer's first name (if explode_name=True)
            - last_name: golfer's last name (if explode_name=True)
            - suffix: golfer's suffix (if explode_name=True) 
        """
        # Generate params and endpoint
        endpoint = 'player-decompositions'
        params = {
            'key': self.api_key,
            'file_format': 'json',
            'tour': tour
        }

        # Call __connect_api function
        players = self.__connect_api(endpoint_name=endpoint,
                                     params=params,
                                     prefix='preds'
        )

        # Combine details
        player_deets = pd.json_normalize(players['players'])
        basic_deets = players.drop(['players', 'notes'], axis=1)
        df = pd.concat([basic_deets, player_deets], axis=1)

        # Expand name if desired
        if explode_name:
            df = self._parse_name(df, 'player_name', drop_column=True)

        return df

    def get_player_skill_ratings(self, explode_name=True):
        """
        Returns our estimate and rank for each skill for all players with sufficient Shotlink measured rounds 
        (at least 30 rounds in the last year or 50 in the last 2 years).

        Parameters
        ----------
        explode_name : bool, default=True
            Expands name into first, last name and suffix.

        Returns
        -------
        pd.DataFrame with columns
            - last_updated : datetime, last datetime that this dataframe was updated
            - dg_id : int, datagolf id
            - driving_acc : float, TODO
            - driving_dist : float, TODO
            - sg_app : float, player shots gained "Approach to Green"
            - sg_arg : float, player shots gained "Around the Green"
            - sg_ott : float, player shots gained "Off the Tee"
            - sg_putt : float, player shots gained "Putting"
            - sg_total : float, player combined shots gained
            - player_name: golfer's name (if explode_name=False)
            - first_name: golfer's first name (if explode_name=True)
            - last_name: golfer's last name (if explode_name=True)
            - suffix: golfer's suffix (if explode_name=True)
        """
        # Generate params and endpoint
        endpoint = 'skill-ratings'
        params = {
            'key': self.api_key,
            'display': 'value',
            'file_format': 'json'
        }

        # Call __connect_api function
        players = self.__connect_api(endpoint_name=endpoint,
                                     params=params,
                                     prefix='preds'
        )

        # Combine details
        player_deets = pd.json_normalize(players['players'])
        basic_deets = players.drop(['players'], axis=1)
        df = pd.concat([basic_deets, player_deets], axis=1)

        # Expand name if desired
        if explode_name:
            df = self._parse_name(df, 'player_name', drop_column=True)

        return df

    def get_approach_skill(self, period='l24', explode_name=True):
        """
        Returns detailed player-level approach performance stats (strokes-gained per shot, proximity, GIR, 
        good shot rate, poor shot avoidance rate) across various yardage/lie buckets.

        Parameters
        ----------
        period : {'l[number months]'}, default='l24'
            Specifies time period to sample over. Defaults to last 24 months 'l24'.
        explode_name : bool, default=True
            Expands name into first, last name and suffix.

        Returns
        -------
        pd.DataFrame with columns
            - last_updated : datetime, last datetime that this dataframe was updated
            - time_period  : float, TODO
            - 100_150_fw_gir_rate : float, TODO
            - 100_150_fw_good_shot_rate : float, TODO
            - 100_150_fw_low_data_indicator : float, TODO
            - 100_150_fw_poor_shot_avoid_rate : float, TODO
            - 100_150_fw_proximity_per_shot : float, TODO
            - 100_150_fw_sg_per_shot : float, TODO
            - 100_150_fw_shot_count : float, TODO
            - 150_200_fw_gir_rate : float, TODO
            - 150_200_fw_good_shot_rate : float, TODO
            - 150_200_fw_low_data_indicator : float, TODO
            - 150_200_fw_poor_shot_avoid_rate : float, TODO
            - 150_200_fw_proximity_per_shot : float, TODO
            - 150_200_fw_sg_per_shot : float, TODO
            - 150_200_fw_shot_count : float, TODO
            - 50_100_fw_gir_rate : float, TODO
            - 50_100_fw_good_shot_rate : float, TODO
            - 50_100_fw_low_data_indicator : float, TODO
            - 50_100_fw_poor_shot_avoid_rate : float, TODO
            - 50_100_fw_proximity_per_shot : float, TODO
            - 50_100_fw_sg_per_shot : float, TODO
            - 50_100_fw_shot_count : float, TODO
            - dg_id : int, datagolf id
            - over_150_rgh_gir_rate : float, TODO
            - over_150_rgh_good_shot_rate : float, TODO
            - over_150_rgh_low_data_indicator : float, TODO
            - over_150_rgh_poor_shot_avoid_rate : float, TODO
            - over_150_rgh_proximity_per_shot : float, TODO
            - over_150_rgh_sg_per_shot : float, TODO
            - over_150_rgh_shot_count : float, TODO
            - over_200_fw_gir_rate : float, TODO
            - over_200_fw_good_shot_rate : float, TODO
            - over_200_fw_low_data_indicator : float, TODO
            - over_200_fw_poor_shot_avoid_rate : float, TODO
            - over_200_fw_proximity_per_shot : float, TODO
            - over_200_fw_sg_per_shot : float, TODO
            - over_200_fw_shot_count : float, TODO
            - under_150_rgh_gir_rate : float, TODO
            - under_150_rgh_good_shot_rate : float, TODO
            - under_150_rgh_low_data_indicator : float, TODO
            - under_150_rgh_poor_shot_avoid_rate : float, TODO
            - under_150_rgh_proximity_per_shot : float, TODO
            - under_150_rgh_sg_per_shot : float, TODO
            - under_150_rgh_shot_count : float, TODO
            - player_name: golfer's name (if explode_name=False)
            - first_name: golfer's first name (if explode_name=True)
            - last_name: golfer's last name (if explode_name=True)
            - suffix: golfer's suffix (if explode_name=True)
        """
        # Generate params and endpoint
        endpoint = 'approach-skill'
        params = {
            'key': self.api_key,
            'period': period,
            'file_format': 'json'
        }

        # Call __connect_api function
        players = self.__connect_api(endpoint_name=endpoint,
                                     params=params,
                                     prefix='preds'
        )

        # Combine details
        player_deets = pd.json_normalize(players['data'])
        basic_deets = players.drop(['data'], axis=1)
        df = pd.concat([basic_deets, player_deets], axis=1)

        # Expand name if desired
        if explode_name:
            df = self._parse_name(df, 'player_name', drop_column=True)

        return df

    def get_fantasy(self, tour='pga', site=None, slate='main', explode_name=True, include_notes=False):
        """
        Parameters
        ----------
        tour : {'pga', 'euro', 'kft', 'opp', 'alt'}, default='pga'
            Specifies the tour.
        site : {'draftkings', 'fanduel', 'yahoo'}, default='draftkings'
            Specifies the site in which the fantasy data is applied.
        slate : {'main', 'showdown', 'showdown_late', 'weekend', 'captain'}, default='main'
            Specifies the slate. Non 'main' slates are only available for site='draftkings'.
        explode_name : bool, default=True
            Expands name into first, last name and suffix.
        include_notes : bool, default=False
            Whether or not to include the `note` key returned from the api call. Usually this note
            does not contain critical information related to the predictions and, therefore, this
            input defaults to False

        Returns
        -------
        pd.DataFrame with columns
            - event_name: str, tour event name
            - last_updated : datetime, last datetime that this dataframe was updated
            - note : str, notes about the call to the api (if `include_notes`=True)
            - site : str, dfs site applicable to this analysis
            - slate : str, dfs site slate applicable to this analysis
            - tour : str, tour for this analysis
            - dg_id : int, datagolf id
            - early_late_wave : int, starting wave. 1=(day 1 early, day 2 late)
            - player_name: golfer's name (if explode_name=False)
            - first_name: golfer's first name (if explode_name=True)
            - last_name: golfer's last name (if explode_name=True)
            - suffix: golfer's suffix (if explode_name=True)
            - proj_ownership: float, model projected ownership percentage
            - proj_points: float, model projected points during tournament
            - r1_teetime: str, round 1 tee time
            - salary: int, player salary
            - site_name_id: str, UNSURE OF THE PURPOSE FOR COLUMN
        """
        
        # Generate params and endpoint
        endpoint = 'fantasy-projection-defaults'
        params = {
            'key': self.api_key,
            'tour': tour,
            'site': site,
            'slate': slate,
            'file_format': 'json'
        }

        # Call __connect_api function
        players = self.__connect_api(endpoint_name=endpoint,
                                     params=params,
                                     prefix='preds'
        )

        # Combine details
        player_deets = pd.json_normalize(players['projections'])
        basic_deets = players.drop(['projections'], axis=1)
        df = pd.concat([basic_deets, player_deets], axis=1)

        # Expand name if desired
        if explode_name:
            df = self._parse_name(df, 'player_name', drop_column=True)

        if ~include_notes:
            df = df.drop('note', axis=1)

        return df

    # def get_live_model_predictions(self, tour='pga', dead_heat=False, odds_format='percent'):
    #     """
    #     Returns live (updating at 5 minute intervals) finish probabilities for ongoing PGA and European Tour tournaments.

    #     The data from this method corresponds to Live Predictive Model page https://datagolf.com/live-model/pga-tour

    #     Parameters
    #     ----------
    #     tour : {'pga', 'euro', 'kft', 'opp', 'alt'}, default='pga'
    #         Specifies the tour.
    #     dead_heat : bool or {'yes', 'no'}, default=False
    #         Whether or not to adjust for dead-heat rules. Dead head explanation:
    #         The simplest bet types are those where you receive a payout equal to the offered odds if you win, and 
    #         receive nothing otherwise. This payout structure exists for matchup bets where a separate bet for a tie 
    #         is offered, for example. However, for bets on finish positions (e.g. to finish in the Top 20), for 3-balls, 
    #         and for some other bet types, 'dead-heat' rules typically apply. These rules specify the payout in the event 
    #         of ties between golfers. In a 3-ball, if there is a tie for low score (between 2, or all 3, of the golfers), 
    #         the payout you receive will be divided by the number of golfers involved in the tie; if you bet 1 unit on 
    #         golfer A at European odds of 4.0, and there is a 3-way tie in the 3-ball, your payout will be equal to 4/3, 
    #         for a profit of 4/3 - 1 = 0.33 units. For finish position bets, the same logic applies: if 2 golfers tie for 
    #         20th place the payout will be halved; if 7 golfers tied for 17th place, the payout would be equal to 4/7 of 
    #         the full bet. More generally, the fraction to be paid out is equal to (num positions paid)/(num golfers tied). 
    #         The expected value calculations in the Scratch Tools for 3-balls and finish position bets take into account 
    #         dead-heat rules.
    #     odds_format : {'percent', 'american', 'decimal', 'fraction'}, default='percent'
    #         Specifies the odds format.

    #     Returns
    #     -------
    #     pd.DataFrame with columns
    #         - course_name : str, name of the course

    #     """
    #     # https://feeds.datagolf.com/preds/in-play?tour=[ tour ]&dead_heat=[ dead_heat ]&odds_format=[ odds_format ]&file_format=[ file_format ]&key=502b38149b492f7ad148e0f20e83

    #     # Generate params and endpoint
    #     endpoint = 'approach-skill'
    #     params = {
    #         'key': self.api_key,
    #         'tour': tour,
    #         'site': site,
    #         'slate': slate,
    #         'file_format': 'json'
    #     }

    #     # Call __connect_api function
    #     players = self.__connect_api(endpoint_name=endpoint,
    #                                  params=params,
    #                                  prefix='preds'
    #     )        

## NEED TO STASH THE RETURNING DATAFRAMES TO LIMIT THE NEED FOR API REQUESTS.


class DataGolfAPIInputError(Exception):
    """Custom exception for issues with input into the Datagolf API"""
    pass

class DataGolfAPIResponseError(Exception):
    """Custom exception for issues with unrecognized response from the API."""
    pass


"""
Running list of questions for datagolf admins
---------------------------------------------
- API tour does not accept LIV but it is available on website...is that functionality coming?
- pre-tournament endpoint is not accepting add_position. Needs better example options if possible
"""