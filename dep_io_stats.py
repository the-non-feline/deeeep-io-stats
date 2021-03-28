import grequests
import discord
import dataset
import asyncio
import sys
import requests
import time
import random
import re
import dateutil.parser as parser
import json
import logging
import math
import json

import logs
from logs import debug
import tools
import commands
from chars import c
import trimmed_embed
import report
import habitat

class Dep_io_Stats(discord.Client): 
    REV_CHANNEL_SENTINEL = 'none' 
    REV_CHANNEL_KEY = 'rev_channel' 
    REV_INTERVAL_KEY = 'rev_interval' 
    REV_LAST_CHECKED_KEY = 'rev_last_checked' 

    DEFAULT_PREFIX = ',' 
    MAX_PREFIX = 5
    PREFIX_SENTINEL = 'none' 

    LINK_SENTINEL = 'remove' 
    LINK_HELP_IMG = 'https://cdn.discordapp.com/attachments/493952969277046787/796576600413175819/linking_instructions.png' 
    INVITE_LINK = 'https://discord.com/oauth2/authorize?client_id=796151711571116042&permissions=347136&scope=bot' 

    DATE_FORMAT = '%B %d, %Y' 
    REV_LOG_TIME_FORMAT = '%m-%d-%Y at %I:%M:%S %p' 
    MESSAGE_LOG_TIME_FORMAT = REV_LOG_TIME_FORMAT

    MAX_TITLE = 256
    MAX_DESC = 2048
    MAX_FIELD_VAL = 1024
    TRAIL_OFF = '...' 
    MAX_LOG = 1000000
    MAX_SEARCH_TIME = 60
    MAX_SKIN_SUGGESTIONS = 10

    OWNER_ID = 315682382147485697

    MENTION_REGEX = '\A<@!?(?P<member_id>[0-9]+)>\Z' 
    CHANNEL_REGEX = '\A<#(?P<channel_id>[0-9]+)>\Z' 

    DATA_URL_TEMPLATE = 'https://api.deeeep.io/users/{}' 
    PFP_URL_TEMPLATE = 'https://deeeep.io/files/{}' 
    SERVER_LIST_URL = 'http://api.deeeep.io/hosts?beta=1' 
    MAP_URL_TEMPLATE = 'https://api.deeeep.io/maps/{}' 
    SKINS_LIST_URL = 'https://api.deeeep.io/skins' 
    LOGIN_URL = 'https://api.deeeep.io/auth/local/signin' 
    SKIN_BOARD_MEMBERS_URL = 'https://api.deeeep.io/users/boardMembers' 
    LOGOUT_URL = 'https://api.deeeep.io/auth/logout' 
    PFP_REGEX = '\A(?:https?://)?(?:www\.)?deeeep\.io/files/(?P<acc_id>[0-9]+)(?:-temp)?\.[0-9A-Za-z]+(?:\?.*)?\Z' 

    DEFAULT_PFP = 'https://deeeep.io/new/assets/placeholder.png' 

    SKIN_ASSET_URL_TEMPLATE = 'https://deeeep.io/assets/skins/{}' 
    CUSTOM_SKIN_ASSET_URL_ADDITION = 'custom/' 
    SKIN_URL_TEMPLATE = 'https://api.deeeep.io/skins/{}' 
    SKIN_REVIEW_TEMPLATE = 'https://api.deeeep.io/skins/{}/review' 

    STONKS_THRESHOLD = 150

    STAT_CHANGE_TRANSLATIONS = {
        'HM': ('healthMultiplier', 'health', '{}'), 
        'DM': ('damageMultiplier', 'damage', '{}'), 
        'DB': ('damageBlock', 'armor', '{}%'), 
        'DR': ('damageReflection', 'damage reflect', '{}%'), 
        'AP': ('armorPenetration', 'armor penetration', '{}%'), 
        'BR': ('bleedReduction', 'bleed reduction', '{}%'), 
        'OT': ('oxygenTime', 'oxygen time', '{}s'), 
        'TT': ('temperatureTime', 'temperature time', '{}s'), 
        'PT': ('pressureTime', 'pressure time', '{}s'), 
        'ST': ('salinityTime', 'salinity time', '{}s'), 
        'SS': ('sizeMultiplier', 'size scale', '{}x'), 
        'HA': ('habitat', 'habitat', '{}'), 
    } 
    OLD_STAT_MULTIPLIERS = {
        'DB': 100, 
        'DR': 100, 
        'AP': 100, 
        'BR': 100, 
    }
    STAT_CHANGE_CONVERTERS = {
        'HM': lambda num: tools.trunc_float(num * 100), 
        'DM': lambda num: tools.trunc_float(num * 20), 
        'SS': lambda num: float(num), 
        'HA': lambda num: habitat.Habitat(num), 
    }

    SKIN_REVIEW_LIST_URL = 'https://api.deeeep.io/skins/pending?t=review' 
    STATS_UNBALANCE_BLACKLIST = ['OT', 'TT', 'PT', 'ST', 'SS', 'HA'] 
    FLOAT_CHECK_REGEX = '\A(?P<abs_val>[-+][0-9]+(?:\.[0-9]+)?)\Z' 
    REDDIT_LINK_REGEX = '\A(?:https?://)?(?:www\.)?reddit\.com/(?:r|u|(?:user))/[0-9a-zA-Z_]+/comments/[0-9a-zA-Z]+/.+/?(?:\?.*)?\Z' 

    MAP_URL_ADDITION = 's/' 
    MAPMAKER_URL_TEMPLATE = 'https://mapmaker.deeeep.io/map/{}' 
    MAP_REGEX = '\A(?:(?:https?://)?(?:www\.)?mapmaker\.deeeep\.io/map/)?(?P<map_string_id>[0-9_A-Za-z]+)\Z' 

    PENDING_SKINS_LIST_URL = 'https://api.deeeep.io/skins/pending' 
    PENDING_MOTIONS_URL = 'https://api.deeeep.io/motions/pending?targetType=skin' 
    RECENT_MOTIONS_URL = 'https://api.deeeep.io/motions/recent?targetType=skin' 

    def __init__(self, logs_file_name, storage_file_name, animals_file_name, email, password): 
        self.email = email
        self.password = password

        self.db = dataset.connect(storage_file_name) 
        self.links_table = self.db.get_table('account_links') 
        self.prefixes_table = self.db.get_table('prefixes') 
        self.rev_data_table = self.db.get_table('rev_data') 
        self.blacklists_table = self.db.get_table('blacklists') 
        self.sb_channels_table = self.db.get_table('sb_channels') 

        self.logs_file = open(logs_file_name, mode='w+', encoding='utf-8') 
        self.animals_file_name = animals_file_name

        self.set_animal_stats() 

        handler = logging.StreamHandler(self.logs_file) 

        logs.logger.addHandler(handler) 

        #self.levels_file = open(levels_file_name, mode='r') 

        self.tasks = 0
        self.logging_out = False

        self.readied = False
        self.token = None

        self.auto_rev_process = None

        super().__init__(activity=discord.Game(name='starting up'), status=discord.Status.dnd) 
    
    def animal_stats(self): 
        with open(self.animals_file_name, mode='r') as file: 
            return json.load(file) 
    
    def set_animal_stats(self): 
        self.temp_animal_stats = self.animal_stats() 

        debug('set animal stats') 
    
    def find_animal(self, animal_id): 
        stats = self.temp_animal_stats

        return stats[animal_id] 
    
    def prefix(self, c): 
        p = self.prefixes_table.find_one(guild_id=c.guild.id) 
        
        if p: 
            return p['prefix'] 
        else: 
            return self.DEFAULT_PREFIX
    
    def blacklisted(self, c, blacklist_type, target): 
        b_entry = self.blacklists_table.find_one(guild_id=c.guild.id, type=blacklist_type, target=target) 

        return b_entry
    
    def rev_channel(self): 
        c_entry = self.rev_data_table.find_one(key=self.REV_CHANNEL_KEY) 

        if c_entry: 
            c_id = c_entry['channel_id'] 

            c = self.get_channel(c_id) 

            return c
    
    def is_sb_channel(self, channel_id): 
        c_entry = self.sb_channels_table.find_one(channel_id=channel_id) 

        return c_entry
    
    async def send(self, c, *args, **kwargs): 
        try: 
            return await c.send(*args, **kwargs) 
        except discord.errors.Forbidden: 
            debug('that was illegal') 
    
    async def logout(self): 
        if self.auto_rev_process: 
            self.auto_rev_process.cancel() 
        
        await self.change_presence(status=discord.Status.offline)
        
        self.logs_file.close() 
        #self.levels_file.close() 

        await super().logout() 
    
    def log_out_acc(self): 
        if self.token: 
            former_token = self.token

            self.token = None

            debug(f'relinquished token ({former_token})') 

        ''' 
        logout_request = grequests.request('GET', self.LOGOUT_URL, headers={
            'Authorization': f'Bearer {self.token}', 
        }) 

        result = self.async_get(logout_request)[0] 

        debug(f'logout of Deeeep.io account status: {result}')
        ''' 
    
    async def first_task_start(self): 
        self.set_animal_stats() 
    
    async def last_task_end(self): 
        debug('f') 

        self.log_out_acc() 

        logs.trim_file(self.logs_file, self.MAX_LOG) 

        if self.logging_out: 
            await self.logout() 
    
    async def edit_tasks(self, amount): 
        try: 
            if self.tasks == 0: 
                await self.first_task_start() 
            
            self.tasks += amount

            debug(f'now running {self.tasks} tasks') 

            debug('g') 

            if self.tasks == 0: 
                await self.last_task_end() 
        except asyncio.CancelledError: 
            raise
        except: 
            debug('', exc_info=True) 
    
    def task(func): 
        async def task_func(self, *args, **kwargs): 
            await self.edit_tasks(1) 

            try: 
                await func(self, *args, **kwargs) 
            except: 
                debug('', exc_info=True) 
            
            await self.edit_tasks(-1) 
        
        return task_func
    
    def requires_owner(func): 
        async def req_owner_func(self, c, m, *args): 
            if m.author.id == self.OWNER_ID: 
                return await func(self, c, m, *args) 
            else: 
                await self.send(c, content='no u (owner-only command) ', reference=m) 
        
        return req_owner_func
    
    @staticmethod
    def has_perms(req_all, req_one, perms): 
        for perm in req_all: 
            if not getattr(perms, perm): 
                return False
        
        if req_one: 
            for perm in req_one: 
                if getattr(perms, perm): 
                    return True
            else: 
                return False
        else: 
            return True
    
    def requires_perms(req_all=(), req_one=()): 
        def decorator(func): 
            async def req_perms_func(self, c, m, *args): 
                author_perms = c.permissions_for(m.author) 

                if self.has_perms(req_all, req_one, author_perms): 
                    return await func(self, c, m, *args) 
                else: 
                    req_all_str = f"all of the following permissions: {tools.format_iterable(req_all, formatter='`{}`')}" 
                    req_one_str = f"at least one of the following permissions: {tools.format_iterable(req_one, formatter='`{}`')}" 

                    if req_one and req_all: 
                        req_str = req_all_str + ' and ' + req_one_str
                    elif req_all: 
                        req_str = req_all_str
                    else: 
                        req_str = req_one_str
                    
                    await self.send(c, content=f'You need {req_str} to use this command', reference=m) 
            
            return req_perms_func
        
        return decorator
    
    def requires_sb_channel(func): 
        async def req_channel_func(self, c, m, *args): 
            if self.is_sb_channel(c.id): 
                return await func(self, c, m, *args) 
            else: 
                await self.send(c, content="This command is reserved for Skin Board channels.", reference=m) 
        
        return req_channel_func
    
    async def default_args_check(self, c, m, *args): 
        return True

    def command(name, definite_usages={}, indefinite_usages={}, public=True): 
        def decorator(func): 
            command_obj = commands.Command(func, name, definite_usages, indefinite_usages, public) 

            return command_obj
        
        return decorator
    
    '''
    def command(name, req_params=(), optional_params=(), args_check=None): 
        total_params = len(req_params) + len(optional_params) 

        def decorator(func): 
            async def comm_func(self, c, m, *args): 
                if (len(req_params) <= len(args) <= total_params): 
                    await func(self, c, m, *args) 
                else: 
                    usage = self.prefix(c) + name

                    if total_params > 0: 
                        total_params_list = [f'({param})' for param in req_params] + [f'[{param}]' for param in optional_params] 

                        usage += ' ' + tools.format_iterable(total_params_list, sep=' ') 

                    await self.send(c, content=f"the correct way to use this command is `{usage}`. ") 
            
            COMMANDS[name] = comm_func

            return comm_func
        
        return decorator
    ''' 
    
    '''
    def sync_get(self, url): 
        json = None

        try: 
            data = requests.get(url) 

            #debug(data.text) 

            if data.ok and data.text: 
                json = data.json() 

            #debug('z') 
        except requests.ConnectionError: 
            debug('connection error') 

            debug('', exc_info=True) 
        
        return json
    ''' 
    
    def async_get(self, *all_requests): 
        requests_list = [] 

        for request in all_requests: 
            if type(request) is str: # plain url
                to_add = grequests.get(request) 
            elif type(request) is tuple: # (method, url) 
                to_add = grequests.request(*request) 
            else: 
                to_add = request
            
            requests_list.append(to_add) 
        
        def handler(request, exception): 
            debug('connection error') 
            debug(exception) 

        datas = grequests.map(requests_list, exception_handler=handler) 

        #debug(datas) 

        jsons = [] 

        for data in datas: 
            to_append = None
            
            if data: 
                if data.ok and data.text: 
                    to_append = data.json() 
                else: 
                    debug(data.text) 
            else: 
                debug('connection error, no data') 

            jsons.append(to_append) 

        #debug(jsons) 

        return jsons
    
    def get_acc_data(self, acc_id): 
        url = self.DATA_URL_TEMPLATE.format(acc_id) 

        return self.async_get(url)[0] 
    
    def get_map_list(self, list_json): 
        #debug(list_json) 

        map_set = set() 
        
        if list_json: 
            iterator = (server['map_id'] for server in list_json) 

            map_set.update(iterator) 
        
        return map_set
    
    def get_map_urls(self, *map_ids): 
        urls = [self.MAP_URL_TEMPLATE.format(map_id) for map_id in map_ids] 
        
        return urls
    
    def get_map_contribs(self, map_jsons, acc_id): 
        #debug(server_list) 

        contrib_names = [] 

        for map_json in map_jsons: 
            if map_json: 
                #debug(map_json['string_id']) 
                #debug(map_json['user_id']) 
                #debug(acc_id) 

                if str(map_json['user_id']) == acc_id: 
                    contrib_names.append(map_json['string_id']) 
        
        #debug(contrib_names) 
            
        return contrib_names
    
    def get_skin_contribs(self, skins_list, acc_id): 
        contrib_names = [] 

        if skins_list: 
            for skin in skins_list: 
                if str(skin['user_id']) == acc_id: 
                    contrib_names.append(skin['name']) 
        
        return contrib_names
    
    def get_skin_board_role(self, members_list, acc_id): 
        role = None

        if members_list: 
            prev_member_id = None
            reached_manager = False

            for member in members_list: 
                member_id = member['id'] 

                #debug(member_id) 

                if prev_member_id and prev_member_id > member_id: 
                    reached_manager = True
                
                if str(member_id) == acc_id: 
                    position = 'Manager' if reached_manager else 'Member' 
                    role = f'Skin Board {position}' 

                    break
                
                prev_member_id = member_id
        
        return role
    
    def get_contribs(self, acc, acc_id, map_list, skins_list): 
        contribs = [] 

        map_contribs = self.get_map_contribs(map_list, acc_id) 

        if map_contribs: 
            map_str = tools.format_iterable(map_contribs, formatter='`{}`') 

            contribs.append(f'Created map(s) {map_str}') 
        
        skin_contribs = self.get_skin_contribs(skins_list, acc_id) 

        if skin_contribs: 
            skin_str = tools.format_iterable(skin_contribs, formatter='`{}`') 

            contribs.append(f'Created skin(s) {skin_str}') 
        
        #debug(contribs) 
        
        return contribs
    
    def get_roles(self, acc, acc_id, members_list): 
        roles = [] 

        skin_board_role = self.get_skin_board_role(members_list, acc_id) 

        if skin_board_role: 
            roles.append(skin_board_role) 
        
        if acc: 
            if acc['beta']: 
                roles.append(f'Beta Tester') 
        
        return roles
    
    def get_all_acc_data(self, acc_id): 
        acc_url = self.DATA_URL_TEMPLATE.format(acc_id) 
        server_list_url = self.SERVER_LIST_URL
        skins_list_url = self.SKINS_LIST_URL

        if not self.token: 
            login_url = self.LOGIN_URL

            login_request = grequests.request('POST', login_url, data={
                'email': self.email, 
                'password': self.password, 
            }) 

            acc_json, server_list, skins_list, login_json = self.async_get(acc_url, server_list_url, skins_list_url, login_request) 

            if login_json: 
                if not self.token: 
                    self.token = login_json['token'] 

                    debug(f'fetched token ({self.token})') 
                else: 
                    debug(f'seems like another process got the token ({self.token}) already') 
            else: 
                debug(f'error fetching token, which is currently ({self.token})') 
        else: 
            debug(f'already have token ({self.token})') 

            acc_json, server_list, skins_list = self.async_get(acc_url, server_list_url, skins_list_url) 

        map_list = self.get_map_list(server_list) 
        map_urls = self.get_map_urls(*map_list) 
        
        round_2_urls = map_urls.copy() 

        members_list = None

        if self.token: 
            members_request = grequests.request('GET', self.SKIN_BOARD_MEMBERS_URL, headers={
                'Authorization': f'Bearer {self.token}', 
            }) 

            round_2_urls.append(members_request) 

            *map_jsons, members_list = self.async_get(*round_2_urls) 

            #debug(members_list) 
        else: 
            map_jsons = self.async_get(*round_2_urls) 

        contribs = self.get_contribs(acc_json, acc_id, map_jsons, skins_list) 
        roles = self.get_roles(acc_json, acc_id, members_list) 

        return acc_json, contribs, roles
    
    @staticmethod
    def compile_ids_from_motions(motions_list, motion_filter=lambda motion: True): 
        motioned_ids = {} 

        for motion in motions_list: 
            motion_type = motion['target_type'] 

            if motion_type == 'skin' and motion_filter(motion): 
                target_id = motion['target_id'] 
                target_version = motion['target_version'] 

                if target_id in motioned_ids: 
                    motioned_ids[target_id].append(target_version) 
                else: 
                    motioned_ids[target_id] = [target_version] 
        
        return motioned_ids
        
    def get_pending_skins(self, *filters): 
        self.get_review_token() 

        pending_motions = rejected_motions = None
        
        if self.token: 
            pending_motions_request = grequests.request('GET', self.PENDING_MOTIONS_URL, headers={
                'Authorization': f'Bearer {self.token}', 
            }) 
            rejected_motions_request = grequests.request('GET', self.RECENT_MOTIONS_URL, headers={
                'Authorization': f'Bearer {self.token}', 
            }) 

            pending_list, pending_motions, rejected_motions = self.async_get(self.PENDING_SKINS_LIST_URL, pending_motions_request, rejected_motions_request) 
        else: 
            pending_list = self.async_get(self.PENDING_SKINS_LIST_URL)[0] 

        unnoticed_pending = None
        upcoming_pending = None
        motioned_pending = None
        rejected_pending = None

        if pending_list is not None: 
            unnoticed_pending = [] 
            upcoming_pending = [] 

            pending_ids = {} 
            rejected_ids = {} 

            if pending_motions is not None: 
                motioned_pending = [] 
                pending_ids = self.compile_ids_from_motions(pending_motions) 
            
            if rejected_motions is not None: 
                rejected_pending = [] 
                rejected_ids = self.compile_ids_from_motions(rejected_motions, motion_filter=lambda motion: motion['rejected']) 

            for pending in pending_list: 
                passed = True

                for skin_filter in filters: 
                    if not skin_filter(pending): 
                        passed = False

                        break
                
                if passed: 
                    unnoticed = True

                    upcoming = pending['upcoming'] 

                    if upcoming: 
                        upcoming_pending.append(pending) 

                        unnoticed = False
                    
                    skin_id = pending['id'] 
                    skin_version = pending['version'] 

                    if skin_id in pending_ids: 
                        motioned_versions = pending_ids[skin_id] 

                        if skin_version in motioned_versions: 
                            motioned_pending.append(pending)  

                            unnoticed = False
                    
                    if skin_id in rejected_ids: 
                        motioned_versions = rejected_ids[skin_id] 

                        if skin_version in motioned_versions: 
                            rejected_pending.append(pending)  

                            unnoticed = False
                    
                    if unnoticed: 
                        unnoticed_pending.append(pending) 
        
        return unnoticed_pending, upcoming_pending, motioned_pending, rejected_pending
    
    def get_skin(self, skins_list, query): 
        suggestions = [] 

        for skin in skins_list: 
            skin_name = skin['name'] 

            lowered_name = skin_name.lower() 
            lowered_query = query.lower() 

            #debug(lowered_name) 
            #debug(lowered_query) 

            if lowered_name == lowered_query: 
                return skin
            elif len(suggestions) == self.MAX_SKIN_SUGGESTIONS: 
                return None
            elif lowered_query in lowered_name: 
                suggestions.append(skin) 
        else: 
            return suggestions
    
    def unbalanced_stats(self, skin): 
        broken = False
        unbalanced = False

        stat_changes = skin['attributes'] 

        if stat_changes: 
            unbalanced = True

            split_changes = stat_changes.split(';') 

            prev_sign = None

            for change_str in split_changes: 
                split = change_str.split('=') 

                if len(split) == 2: 
                    stat, value = split

                    sign = value[0] 
                    abs_value = value[1:] 

                    m = re.compile(self.FLOAT_CHECK_REGEX).match(value) 

                    if not m: 
                        broken = True

                        debug(f'{value} failed regex') 

                    if stat not in self.STATS_UNBALANCE_BLACKLIST: 
                        if prev_sign and prev_sign != sign: 
                            unbalanced = False
                        
                        prev_sign = sign
                else: 
                    broken = True

                    debug(f'{change_str} is invalid')
        
        unbalance_sign = prev_sign if unbalanced else None

        debug(broken) 
        debug(unbalance_sign) 

        return broken, unbalance_sign
    
    def valid_reddit_link(self, link): 
        m = re.compile(self.REDDIT_LINK_REGEX).match(link) 

        return m
    
    def reject_reasons(self, skin): 
        reasons = [] 

        skin_name = skin['name'] 
        skin_id = skin['id'] 

        skin_url = self.SKIN_URL_TEMPLATE.format(skin_id) 

        debug(f'{skin_name}: {skin_url}') 

        reddit_link = skin['reddit_link']

        if not reddit_link: 
            reasons.append('missing Reddit link') 
        elif not self.valid_reddit_link(reddit_link): 
            reasons.append('invalid Reddit link')
        
        broken, unbalance_sign = self.unbalanced_stats(skin) 

        if broken: 
            reasons.append(f'undefined stat changes') 
        
        if unbalance_sign: 
            reasons.append(f'unbalanced stat changes ({unbalance_sign})') 
        
        return reasons
    
    def inspect_skins(self, review_list): 
        rejected = [] 
        reasons = [] 

        for skin in review_list: 
            rej_reasons = self.reject_reasons(skin) 

            if rej_reasons: 
                rejected.append(skin) 
                reasons.append(rej_reasons) 
        
        #debug(rejected) 
        #debug(reasons) 
        
        return rejected, reasons
    
    def get_review_token(self): 
        if not self.token: 
            login_url = self.LOGIN_URL

            login_request = grequests.request('POST', login_url, data={
                'email': self.email, 
                'password': self.password, 
            }) 

            login_json = self.async_get(login_request)[0] 

            if login_json: 
                if not self.token: 
                    self.token = login_json['token'] 

                    debug(f'fetched token ({self.token})') 
                else: 
                    debug(f'seems like another process got the token ({self.token}) already') 
            else: 
                debug(f'error fetching token, which is currently ({self.token})') 
        else: 
            debug(f'already have token ({self.token})') 
    
    def fake_check(self, r, rejected, reasons, list_json, silent_fail): 
        r.add(f'**{len(rejected)} out of {len(list_json)} failed**') 

        if rejected: 
            r.add('') 

            for skin, reason in zip(rejected, reasons): 
                reason_str = tools.format_iterable(reason, formatter='`{}`') 

                skin_id = skin['id'] 

                skin_url = self.SKIN_URL_TEMPLATE.format(skin_id) 

                creator = skin['user'] 
                c_name = creator['name'] 
                c_username = creator['username'] 

                rejection_str = f"**{skin['name']}** (link {skin_url}) by {c_name} ({c_username}) has the following issues: {reason_str}" 

                r.add(rejection_str) 
    
    def real_check(self, r, rejected, reasons, list_json, silent_fail): 
        message = f'**{len(rejected)} out of {len(list_json)} failed**' 

        if not silent_fail: 
            r.add(message) 
        else: 
            debug(message) 

        if rejected: 
            r.add('') 

            rejection_requests = [] 

            for skin in rejected: 
                skin_id = skin['id'] 
                skin_version = skin['version'] 

                url = self.SKIN_REVIEW_TEMPLATE.format(skin_id) 

                rej_req = grequests.request('POST', url, headers={
                    'Authorization': f'Bearer {self.token}', 
                }, data={
                    "version": skin_version, 
                }) 

                rejection_requests.append(rej_req) 
            
            debug(rejection_requests) 
            
            rej_results = self.async_get(*rejection_requests) 

            debug(rej_results) 

            for result, skin, reason in zip(rej_results, rejected, reasons): 
                if result is not None: 
                    rej_type = "Rejection" 
                    color = 0xff0000
                else: 
                    rej_type = "Rejection Attempt" 
                    color = 0xffff00
                
                reason_str = tools.make_list(reason) 

                skin_name = skin['name'] 
                skin_id = skin['id'] 
                skin_url = self.SKIN_URL_TEMPLATE.format(skin_id) 

                skin_link = skin['reddit_link'] 

                if skin_link: 
                    desc = f'[Reddit link]({skin_link})' 
                else: 
                    desc = None

                asset_name = skin['asset'] 

                if asset_name[0].isnumeric(): 
                    asset_name = self.CUSTOM_SKIN_ASSET_URL_ADDITION + asset_name

                asset_url = tools.salt_url(self.SKIN_ASSET_URL_TEMPLATE.format(asset_name)) 
                
                creator = skin['user'] 
                c_name = creator['name'] 
                c_username = creator['username'] 
                c_str = f'{c_name} (@{c_username})' 

                embed = trimmed_embed.TrimmedEmbed(title=skin_name, type='rich', description=desc, url=skin_url, color=color) 

                embed.set_author(name=f'Skin {rej_type}') 

                embed.set_thumbnail(url=asset_url) 
                #embed.add_field(name=f"Image link {c['image']}", value=f'[Image]({asset_url})') 

                embed.add_field(name=f"Creator {c['carpenter']}", value=c_str, inline=False) 
                embed.add_field(name=f"Rejection reasons {c['scroll']}", value=reason_str, inline=False) 

                embed.set_footer(text=f'ID: {skin_id}') 

                r.add(embed) 

                ''' 
                start = f"Rejected {c['x']}" if result is not None else f"Attemped to reject {c['warning']}" 

                reason_str = tools.format_iterable(reason, formatter='`{}`') 

                skin_id = skin['id'] 
                skin_url = self.SKIN_URL_TEMPLATE.format(skin_id) 
                
                creator = skin['user'] 
                c_name = creator['name'] 
                c_username = creator['username'] 

                rejection_str = f"{start} **{skin['name']}** (link {skin_url}) by {c_name} ({c_username}) for the following reasons: {reason_str}" 

                r.add(rejection_str) 
                ''' 
    
    async def check_review(self, c, processor, silent_fail=False): 
        r = report.Report(self, c) 

        self.get_review_token() 

        if self.token: 
            list_request = grequests.request('GET', self.SKIN_REVIEW_LIST_URL, headers={
                'Authorization': f'Bearer {self.token}', 
            }) 

            list_json = self.async_get(list_request)[0] 

            if list_json: 
                rejected, reasons = self.inspect_skins(list_json) 

                processor(r, rejected, reasons, list_json, silent_fail) 
            elif list_json is None: 
                message = 'Error fetching skins.' 

                if not silent_fail: 
                    r.add(message) 
                else: 
                    debug(message) 
            else: 
                message = 'There are no skins to check.'

                if not silent_fail: 
                    r.add(message) 
                else: 
                    debug(message) 
        else: 
            message = 'Error logging in to perform this task. ' 

            if not silent_fail: 
                r.add(message) 
            else: 
                debug(message) 
        
        await r.send_self() 
    
    '''
    def get_animal(self, animal_id): 
        try: 
            obj = json.load(self.levels_file) 
        except json.JSONDecodeError: 
            debug('Error reading levels file', exc_info=True) 
        else: 
            index = int(animal_id) 

            if index < len(obj): 
                animal_obj = obj[int(animal_id)] 

                return animal_obj['name'] 
            else: 
                return animal_id
    ''' 

    async def self_embed(self, channel): 
        prefix = self.prefix(channel) 
        com_list_str = tools.format_iterable(commands.Command.all_commands(public_only=True), formatter='`{}`') 

        guilds = self.guilds
        guild_count = len(guilds) 

        user_count = self.links_table.count() 

        self_user = self.user

        color = discord.Color.random() 

        if self_user: 
            avatar_url = self_user.avatar_url
            discord_tag = str(self_user) 
        else: 
            avatar_url = None
            discord_tag = "Couldn't fetch Discord tag" 
        
        invite_hyperlink = f'[Invite link]({self.INVITE_LINK})' 
        
        embed = trimmed_embed.TrimmedEmbed(title=discord_tag, description=invite_hyperlink, color=color) 

        if avatar_url: 
            url = str(avatar_url) 
            
            salted = tools.salt_url(url) 

            debug(salted) 

            embed.set_thumbnail(url=salted) 

        owner = await self.fetch_user(self.OWNER_ID) 

        if owner: 
            owner_tag = str(owner) 

            embed.add_field(name=f"Creator {c['carpenter']}", value=owner_tag) 
        
        com_list = f'''{com_list_str}

Type `{prefix}{self.send_help.name} <command>` for help on a specified `<command>`''' 

        embed.add_field(name=f"Public commands {c['scroll']}", value=com_list, inline=False) 

        embed.set_footer(text=f'Used by {user_count} users across {guild_count} guilds') 

        return embed
    
    def add_stat_changes(self, embed, stat_changes, animal): 
        stat_changes_list = [] 

        for change in stat_changes.split(';'): 
            split = change.split('=') 

            if len(split) == 2: 
                attribute, diff = split

                translation_format = self.STAT_CHANGE_TRANSLATIONS.get(attribute, None) 

                if translation_format: 
                    key, display_name, formatter = translation_format
                    converter = self.STAT_CHANGE_CONVERTERS.get(attribute, tools.trunc_float) 

                    multiplier = self.OLD_STAT_MULTIPLIERS.get(attribute, 1) 

                    old_value = animal[key] * multiplier

                    old_value_converted = converter(old_value) 

                    old_value_str = formatter.format(old_value_converted) 

                    m = re.compile(self.FLOAT_CHECK_REGEX).match(diff) 

                    if m: 
                        float_diff = float(diff) 

                        new_value = old_value + float_diff

                        new_value_converted = converter(new_value) 
                        
                        new_value_str = formatter.format(new_value_converted) 
                    else: 
                        new_value_str = f'invalid ({diff})' 

                    change_str = f'**{display_name}:** {old_value_str} **->** {new_value_str}' 
                else: 
                    change_str = f'Untranslated change: {change}' 
            else: 
                change_str = f'Invalid change: {change}' 
            
            stat_changes_list.append(change_str) 
        
        stat_changes_str = tools.make_list(stat_changes_list)  

        embed.add_field(name=f"Stat changes {c['change']}", value=stat_changes_str, inline=False) 
        
    def skin_embed(self, skin, direct_api=False): 
        color = discord.Color.random() 

        stat_changes = skin['attributes'] 
        when_created = skin['created_at'] 
        designer_id = skin['designer_id'] 
        animal_id = skin['fish_level'] 
        ID = skin['id'] 
        price = skin['price'] 
        sales = skin['sales'] 
        last_updated = skin['updated_at'] 
        version = skin['version'] 

        asset_name = skin['asset'] 

        animal = self.find_animal(animal_id) 

        animal_name = animal['name'] 

        desc = None
        reddit_link = None
        category = None
        season = None
        usable = None

        user = None

        if not direct_api: 
            skin_url = self.SKIN_URL_TEMPLATE.format(ID) 

            skin_json = self.async_get(skin_url)[0] 
        else: 
            skin_json = skin

        if skin_json: 
            desc = skin_json['description'] 

            #debug(desc) 

            reddit_link = skin_json['reddit_link'] 
            category = skin_json['category'] 
            season = skin_json['season'] 
            usable = skin_json['usable'] 

            user = skin_json['user'] 

        #debug(desc) 

        embed = trimmed_embed.TrimmedEmbed(title=skin['name'], description=desc, color=color, url=reddit_link) 

        if asset_name[0].isnumeric(): 
            asset_name = self.CUSTOM_SKIN_ASSET_URL_ADDITION + asset_name

        asset_url = tools.salt_url(self.SKIN_ASSET_URL_TEMPLATE.format(asset_name)) 

        debug(asset_url) 

        embed.set_image(url=asset_url) 

        #animal_name = self.get_animal(animal_id) 

        embed.add_field(name=f"Animal {c['fish']}", value=animal_name) 
        embed.add_field(name=f"Price {c['deeeepcoin']}", value=f'{price:,}') 

        sales_emoji = c['stonkalot'] if sales >= self.STONKS_THRESHOLD else c['stonkanot'] 

        embed.add_field(name=f"Sales {sales_emoji}", value=f'{sales:,}') 

        if stat_changes: 
            self.add_stat_changes(embed, stat_changes, animal) 

        if category: 
            embed.add_field(name=f"Category {c['folder']}", value=category) 

        if season: 
            embed.add_field(name=f"Season {c['calendar']}", value=season) 
        
        if usable is not None: 
            usable_emoji = c['check'] if usable else c['x'] 

            embed.add_field(name=f"Usable {usable_emoji}", value=usable) 
        
        if when_created: 
            date_created = parser.isoparse(when_created) 

            embed.add_field(name=f"Date created {c['tools']}", value=date_created.strftime(self.DATE_FORMAT)) 

        version_str = str(version) 
        version_inline = True

        if last_updated: 
            date_updated = parser.isoparse(last_updated) 

            version_str += f' (updated {date_updated.strftime(self.DATE_FORMAT)})' 
            version_inline = False
        
        embed.add_field(name=f"Version {c['wrench']}", value=version_str, inline=version_inline) 

        if user: 
            user_name = user['name']
            user_username = user['username'] 
            user_pfp = user['picture'] 

            creator = f'{user_name} (@{user_username})' 

            if not user_pfp: 
                user_pfp = self.DEFAULT_PFP
            else: 
                user_pfp = self.PFP_URL_TEMPLATE.format(user_pfp)
            
            pfp_url = tools.salt_url(user_pfp) 

            debug(pfp_url) 

            embed.set_author(name=creator, icon_url=pfp_url) 

        embed.set_footer(text=f"ID: {ID}") 

        return embed
    
    def acc_embed(self, acc_id): 
        acc, contribs, roles = self.get_all_acc_data(acc_id) 

        color = discord.Color.random() 

        if acc: 
            title = f"{acc['name']} (@{acc['username']})"  

            desc = acc['description'] 

            pfp = acc['picture'] 

            #debug(pfp_url) 
            
            kills = acc['kill_count'] 
            max_score = acc['highest_score'] 
            coins = acc['coins'] 

            #debug(hex(color)) 

            embed = trimmed_embed.TrimmedEmbed(title=title, type='rich', description=desc, color=color) 
            
            if not pfp: 
                pfp = self.DEFAULT_PFP
            else: 
                pfp = self.PFP_URL_TEMPLATE.format(pfp) 
            
            pfp_url = tools.salt_url(pfp) 

            debug(pfp_url) 
            
            embed.set_image(url=pfp_url) 

            embed.add_field(name=f"Kills {c['iseedeadfish']}", value=f'{kills:,}') 
            embed.add_field(name=f"Highscore {c['first_place']}", value=f'{max_score:,}') 
            embed.add_field(name=f"Coins {c['deeeepcoin']}", value=f'{coins:,}') 

            when_created = acc['date_created'] 
            when_last_played = acc['date_last_played'] 

            if when_created: 
                date_created = parser.isoparse(when_created) 

                embed.add_field(name=f"Date created {c['baby']}", value=date_created.strftime(self.DATE_FORMAT)) 

            if when_last_played: 
                date_last_played = parser.isoparse(when_last_played) 

                embed.add_field(name=f"Date last played {c['video_game']}", value=date_last_played.strftime(self.DATE_FORMAT)) 
        else: 
            embed = trimmed_embed.TrimmedEmbed(title='Error fetching account statistics', type='rich', description="There was an error fetching account statistics. ", color=color) 

            embed.add_field(name="Why?", value="This usually happens when the game isn't working. ") 
            embed.add_field(name="What now?", value="Don't spam this command. Just try again when the game works again. ") 
        
        embed.set_footer(text=f'ID: {acc_id}') 

        if contribs: 
            contribs_str = tools.make_list(contribs) 

            embed.add_field(name=f"Contributions {c['heartpenguin']}", value=contribs_str, inline=False) 
        
        if roles: 
            roles_str = tools.format_iterable(roles) 

            embed.add_field(name=f"Roles {c['cooloctopus']}", value=roles_str, inline=False)

        return embed
    
    def count_objects(self, objs): 
        class Counter: 
            total_obj = 0
            total_points = 0
            counters = {} 

            def __init__(self, layer_name, display_name=None): 
                self.layer_name = layer_name
                self.display_name = display_name

                self.obj = 0
                self.points = 0

                self.counters[layer_name] = self
            
            def add(self, element): 
                points = 1

                if 'points' in element: 
                    points = len(element['points']) 

                self.obj += 1
                self.__class__.total_obj +=1

                self.points += points
                self.__class__.total_points += points
            
            def get_display_name(self): 
                if self.display_name: 
                    return self.display_name
                else: 
                    return self.layer_name.replace('-', ' ') 
            
            @classmethod
            def add_element(cls, element): 
                layer_id = element['layerId'] 

                if layer_id in cls.counters: 
                    counter = cls.counters[layer_id] 
                else: 
                    counter = cls(layer_id) 
                
                counter.add(element) 

        [Counter.add_element(element) for element in objs] 

        result_list = [f'{counter.obj:,} {counter.get_display_name()} ({counter.points:,} points)' for counter in Counter.counters.values()] 

        result_list.insert(0, f'**{Counter.total_obj:,} total objects ({Counter.total_points:,} points)**') 

        return result_list
    
    def map_embed(self, map_json): 
        color = discord.Color.random() 

        title = map_json['title'] 
        ID = map_json['id'] 
        string_id = map_json['string_id'] 
        desc = map_json['description'] 
        likes = map_json['likes'] 
        objects = map_json['objects'] 
        clone_of = map_json['cloneof_id'] 
        locked = map_json['locked'] 

        when_created = map_json['created_at'] 
        when_updated = map_json['updated_at'] 

        map_data = json.loads(map_json['data']) 
        tags = map_json['tags'] 
        creator = map_json['user'] 

        tags_list = [tag['id'] for tag in tags] 
        creator_name = creator['name'] 
        creator_username = creator['username'] 
        creator_pfp = creator['picture'] 

        world_size = map_data['worldSize'] 
        width = world_size['width'] 
        height = world_size['height'] 

        objs = map_data['screenObjects'] 

        map_link = self.MAPMAKER_URL_TEMPLATE.format(string_id) 

        embed = trimmed_embed.TrimmedEmbed(title=title, description=desc, color=color, url=map_link) 

        embed.add_field(name=f"Likes {c['thumbsup']}", value=f'{likes:,}') 
        
        embed.add_field(name=f"Dimensions {c['triangleruler']}", value=f'{width} x {height}') 

        if 'settings' in map_data: 
            settings = map_data['settings'] 
            gravity = settings['gravity'] 

            embed.add_field(name=f"Gravity {c['down']}", value=f'{gravity:,}') 

        obj_count_list = self.count_objects(objs) 

        obj_count_str = tools.make_list(obj_count_list) 

        embed.add_field(name=f"Object count {c['scroll']}", value=obj_count_str, inline=False) 

        creator_str = f'{creator_name} (@{creator_username})'

        if not creator_pfp: 
            creator_pfp = self.DEFAULT_PFP
        else: 
            creator_pfp = self.PFP_URL_TEMPLATE.format(creator_pfp) 
        
        pfp_url = tools.salt_url(creator_pfp) 

        debug(pfp_url) 

        embed.set_author(name=creator_str, icon_url=pfp_url) 

        if clone_of: 
            clone_url = self.MAP_URL_TEMPLATE.format(clone_of) 

            clone_json = self.async_get(clone_url)[0] 

            if clone_json: 
                clone_title = clone_json['title'] 
                clone_string_id = clone_json['string_id'] 

                clone_link = self.MAPMAKER_URL_TEMPLATE.format(clone_string_id) 

                embed.add_field(name=f"Cloned from {c['notes']}", value=f'[{clone_title}]({clone_link})') 
        
        if when_created: 
            date_created = parser.isoparse(when_created) 

            embed.add_field(name=f"Date created {c['tools']}", value=date_created.strftime(self.DATE_FORMAT)) 
        
        if when_updated: 
            date_updated = parser.isoparse(when_updated) 

            embed.add_field(name=f"Date last updated {c['wrench']}", value=date_updated.strftime(self.DATE_FORMAT)) 
        
        lock_emoji = c['lock'] if locked else c['unlock'] 
        
        embed.add_field(name=f"Locked {lock_emoji}", value=locked) 

        if tags_list: 
            tags_str = tools.format_iterable(tags_list, formatter='`{}`') 

            embed.add_field(name=f"Tags {c['label']}", value=tags_str, inline=False) 

        embed.set_footer(text=f'''ID: {ID}
String ID: {string_id}''') 

        return embed
    
    def skin_str_list(self, skin_list): 
        str_list = map(lambda skin: f"{skin['name']} (v{skin['version']}) - {self.find_animal(skin['fish_level'])['name']}", skin_list) 

        final_str = tools.make_list(str_list) 

        return final_str
    
    def switch_skin_string(self, skin_list): 
        if skin_list is None: 
            list_str = 'There was an error fetching skins.' 
        elif skin_list: 
            list_str = self.skin_str_list(skin_list) 
        else: 
            list_str = 'There are no skins in this category.' 

        return list_str
    
    def pending_embed(self, filter_names, filters): 
        color = discord.Color.random() 

        pending, upcoming, motioned, rejected = self.get_pending_skins(*filters) 

        if filter_names: 
            filter_names_str = tools.format_iterable(filter_names, formatter='`{}`') 
        else: 
            filter_names_str = '(none)' 

        embed = trimmed_embed.TrimmedEmbed(type='rich', title=f'Pending skins with filters {filter_names_str}', description='Unreleased skins in Creators Center', color=color) 

        pending_str = self.switch_skin_string(pending) 
        
        embed.add_field(name=f"Unnoticed skins ({len(pending)}) {c['ghost']}", value=pending_str, inline=False) 

        upcoming_str = self.switch_skin_string(upcoming) 
        
        embed.add_field(name=f"Upcoming skins ({len(upcoming)}) {c['clock']}", value=upcoming_str, inline=False) 

        motioned_str = self.switch_skin_string(motioned) 
        
        embed.add_field(name=f"Skins in motion ({len(motioned)}) {c['ballot_box']}", value=motioned_str, inline=False) 

        rejected_str = self.switch_skin_string(rejected) 
        
        embed.add_field(name=f"Recently rejected skins ({len(rejected)}) {c['x']}", value=rejected_str, inline=False) 

        return embed
    
    def time_exceeded(self): 
        last_checked_row = self.rev_data_table.find_one(key=self.REV_LAST_CHECKED_KEY) 

        if last_checked_row: 
            interval_row = self.rev_data_table.find_one(key=self.REV_INTERVAL_KEY) 

            if interval_row: 
                last_checked = last_checked_row['time'] 
                interval = interval_row['interval'] 

                current_time = time.time() 

                return current_time - last_checked >= interval
            else: 
                debug('No interval set') 
        else: 
            debug('No last_checked') 

            return True
    
    async def auto_rev(self): 
        time_str = time.strftime(self.REV_LOG_TIME_FORMAT) 

        debug(f'Checked at {time_str}') 

        rev_channel = self.rev_channel() 

        if rev_channel: 
            await self.check_review(rev_channel, self.real_check, silent_fail=True) 
        else: 
            debug('No rev channel set') 
    
    def write_new_time(self): 
        data = {
            'key': self.REV_LAST_CHECKED_KEY, 
            'time': time.time(), 
        } 

        self.rev_data_table.upsert(data, ['key'], ensure=True) 
    
    @task
    async def auto_rev_task(self): 
        await self.auto_rev() 

        self.write_new_time() 
    
    async def auto_rev_loop(self): 
        while True: 
            try: 
                if self.time_exceeded(): 
                    await self.auto_rev_task() 
                
                await asyncio.sleep(1) 
            except asyncio.CancelledError: 
                raise
            except: 
                debug('', exc_info=True) 
    
    async def on_ready(self): 
        self.readied = True

        if not self.auto_rev_process: 
            self.auto_rev_process = self.loop.create_task(self.auto_rev_loop()) 

            debug('created auto rev process') 
        
        await self.change_presence(activity=discord.Game(name='all systems operational'), status=discord.Status.online)
        
        debug('ready') 
    
    def decode_mention(self, c, mention): 
        member_id = None

        if not mention.isnumeric(): 
            m = re.compile(self.MENTION_REGEX).match(mention)

            if m: 
                member_id = m.group('member_id') 
        else: 
            member_id = mention
        
        #debug(member_id) 
        
        return int(member_id) if member_id is not None else None
    
    def decode_channel(self, c, mention): 
        channel_id = None

        if not mention.isnumeric(): 
            m = re.compile(self.CHANNEL_REGEX).match(mention)

            if m: 
                channel_id = m.group('channel_id') 
        else: 
            channel_id = mention
        
        #debug(member_id) 
        
        return int(channel_id) if channel_id is not None else None
    
    async def prompt_for_message(self, c, member_id, choices=None, custom_check=lambda to_check: True, timeout=None,  timeout_warning=10, default_choice=None): 
        mention = '<@{}>'.format(member_id) 

        extension = '{}, reply to this message with '.format(mention) 

        # noinspection PyShadowingNames
        def check(to_check): 
            valid_choice = choices is None or any(((to_check.content.lower() == choice.lower()) for choice in choices)) 
            
            #debug(to_check.channel.id == channel.id) 
            #debug(to_check.author.id == member_id) 
            #debug(valid_choice) 
            #debug(custom_check(to_check)) 
            
            return to_check.channel.id == c.id and to_check.author.id == member_id and valid_choice and custom_check(to_check) 

        to_return = None

        try:
            message = await self.wait_for('message', check=check, timeout=timeout) 
        except asyncio.TimeoutError: 
            await self.send(c, content='{}, time limit exceeded, going with default. '.format(mention)) 

            to_return = default_choice
        else: 
            to_return = message.content
        
        return to_return
    
    @command('stats', definite_usages={
        (): 'View your own stats', 
        ('@<user>',): "View `<user>`'s stats", 
        ('<user_ID>',): "Same as above except with Discord ID instead to avoid pings", 
    }) 
    async def check_stats(self, c, m, user=None): 
        if not user: 
            user_id = m.author.id
        else: 
            user_id = self.decode_mention(c, user) 
        
        #debug(user_id) 

        link = None

        if user_id is not None: 
            if not self.blacklisted(c, 'user', user_id): 
                link = self.links_table.find_one(user_id=user_id) 

                #debug('f') 

                if link: 
                    acc_id = link['acc_id'] 

                    if not self.blacklisted(c, 'account', acc_id): 
                        await self.send(c, embed=self.acc_embed(acc_id)) 
                    else: 
                        await self.send(c, content=f'This account (ID {acc_id}) is blacklisted from being displayed on this server. ', reference=m) 
                    
                elif user_id == m.author.id: 
                    await self.send(c, content=f"You're not linked to an account. Type `{self.prefix(c)}link` to learn how to link an account. ", reference=m) 
                else: 
                    await self.send(c, content=f"This user isn't linked.", reference=m) 
            elif user_id == m.author.id: 
                await self.send(c, content=f"You're blacklisted from displaying your account on this server.", reference=m) 
            else: 
                await self.send(c, content='This user is blacklisted from displaying their account on this server. ', reference=m) 
        else: 
            return True
    
    def convert_target(self, lower_type, target_str): 
        if lower_type == 'user': 
            target = self.decode_mention(c, target_str) 
        elif lower_type == 'account': 
            target = int(target_str) if target_str.isnumeric() else None
        elif lower_type == 'map': 
            target = int(target_str) if target_str.isnumeric() else None
        else: 
            target = None
        
        return target
    
    @command('blacklist', definite_usages={
        ('user', '<mention>'): 'Blacklist the mentioned user from displaying their Deeeep.io account **on this server only**', 
        ('user', '<user_id>'): 'Like above, but with discord ID instead to avoid pings', 
        ('account', '<account_id>'): 'Blacklists the Deeeep.io account with account ID of `<account_id>` from being displayed **on this server only**', 
        ('map', '<map_id>'): 'Blacklists the map with string ID of `<map_id>` from being displayed **on this server only**', 
    }) 
    @requires_perms(req_one=('manage_messages',)) 
    async def blacklist(self, c, m, blacklist_type, target_str): 
        lower_type = blacklist_type.lower() 

        target = self.convert_target(lower_type, target_str) 

        if target: 
            data = {
                'type': lower_type, 
                'guild_id': c.guild.id, 
                'target': target, 
            } 

            self.blacklists_table.upsert(data, ['type', 'guild_id', 'target'], ensure=True) 

            await self.send(c, content=f'Successfully blacklisted {lower_type} `{target}` on this server.') 
        else: 
            return True
    
    @command('unblacklist', definite_usages={
        ('user', '<mention>'): 'Unblacklist the mentioned user from displaying their Deeeep.io account **on this server only**', 
        ('user', '<user_id>'): 'Like above, but with discord ID instead to avoid pings', 
        ('account', '<account_id>'): 'Unblacklists the Deeeep.io account with account ID of `<account_id>` from being displayed **on this server only**', 
        ('map', '<string_id>'): 'Unblacklists the map with string ID of `<string_id>` from being displayed **on this server only**', 
    }) 
    @requires_perms(req_one=('manage_messages',)) 
    async def unblacklist(self, c, m, blacklist_type, target_str): 
        lower_type = blacklist_type.lower() 

        target = self.convert_target(lower_type, target_str) 

        if target: 
            self.blacklists_table.delete(guild_id=c.guild.id, type=lower_type, target=target) 

            await self.send(c, content=f'Successfully unblacklisted {lower_type} `{target}` on this server.') 
        else: 
            return True
    
    @command('skin', indefinite_usages={
        ('<skin name>',): "View the stats of skin with `<skin name>` (e.g. `Albino Cachalot`)", 
    }) 
    async def check_skin(self, c, m, *skin_query): 
        skin_name = ' '.join(skin_query) 

        skins_list_url = self.SKINS_LIST_URL

        skins_list = self.async_get(skins_list_url)[0] 
        
        if skins_list: 
            skin_data = self.get_skin(skins_list, skin_name) 

            skin_json = None
            suggestions_str = '' 

            if type(skin_data) is list: 
                if len(skin_data) == 1: 
                    skin_json = skin_data[0] 
                else: 
                    if skin_data: 
                        skin_names = (skin['name'] for skin in skin_data) 

                        suggestions_str = tools.format_iterable(skin_names, formatter='`{}`') 

                        suggestions_str = f"Maybe you meant one of these? {suggestions_str}" 
                
                debug(f'Suggestions length: {len(skin_data)}') 
            elif skin_data: 
                skin_json = skin_data

                debug('match found') 
            else: 
                debug('limit exceeded') 

            if skin_json: 
                await self.send(c, embed=self.skin_embed(skin_json)) 
            else: 
                text = "That's not a valid skin name. " + suggestions_str

                await self.send(c, content=text) 
        else: 
            await self.send(c, content=f"Can't fetch skins. Most likely the game is down and you'll need to wait until it's fixed. ") 
    
    @command('skinbyid', definite_usages={
        ('<skin_id>',): 'View the stats of the skin with the given `<skin_id>`', 
    }, public=False) 
    @requires_sb_channel
    async def check_skin(self, c, m, skin_id): 
        if skin_id.isnumeric(): 
            skin_url = self.SKIN_URL_TEMPLATE.format(skin_id) 

            skin_json = self.async_get(skin_url)[0] 

            if skin_json: 
                await self.send(c, embed=self.skin_embed(skin_json)) 
            else: 
                await self.send(c, content=f"That's not a valid skin ID (or the game might be down).", reference=m) 
        else: 
            return True
    
    def get_map_string_id(self, query): 
        m = re.compile(self.MAP_REGEX).match(query)

        if m: 
            map_string_id = m.group('map_string_id') 

            return map_string_id
        
        #debug(map_id) 
    
    @command('map', definite_usages={
        ('<map_string_ID>',): "View the stats of the map with the given `<map_string_ID>` (e.g. `sushuimap_v1`)", 
        ('<map_link>',): "Like above, but using the Mapmaker link of the map instead of the name (e.g. `https://mapmaker.deeeep.io/map/ffa_morty`)"
    }) 
    async def check_map(self, c, m, map_query): 
        map_string_id = self.get_map_string_id(map_query) 

        if map_string_id: 
            map_string_id = self.MAP_URL_ADDITION + map_string_id
            
            map_url = self.MAP_URL_TEMPLATE.format(map_string_id) 

            map_json = self.async_get(map_url)[0] 

            if map_json: 
                ID = map_json['id'] 

                if not self.blacklisted(c, 'map', ID): 
                    await self.send(c, embed=self.map_embed(map_json)) 
                else: 
                    await self.send(c, content=f'This map (ID {ID}) is blacklisted from being displayed on this server. ', reference=m)
            else: 
                await self.send(c, content=f"That's not a valid map (or Mapmaker could be broken). ", reference=m) 
        else: 
            return True
    
    @command('fakerev', definite_usages={
        (): 'Not even Fede knows of the mysterious function of this command...', 
    }, public=False) 
    @requires_owner
    async def fake_review(self, c, m): 
        await self.check_review(c, self.fake_check) 
    
    @command('rev', definite_usages={
        (): 'Not even Fede knows of the mysterious function of this command...', 
    }, public=False) 
    @requires_owner
    async def real_review(self, c, m): 
        rev_channel = self.rev_channel() 

        if rev_channel: 
            await self.check_review(rev_channel, self.real_check, silent_fail=True) 
        else: 
            await self.send(c, content='Not set', reference=m) 
    
    async def link_help(self, c, m): 
        await self.send(c, content=f'Click here for instructions on how to link your account. <{self.LINK_HELP_IMG}>', reference=m) 
    
    def get_acc_id(self, query): 
        acc_id = None

        if not query.isnumeric(): 
            m = re.compile(self.PFP_REGEX).match(query)

            if m: 
                acc_id = m.group('acc_id') 
        else: 
            acc_id = query
        
        return acc_id
    
    async def link_dep_acc(self, c, m, query): 
        acc_id = self.get_acc_id(query) 
        
        if acc_id is not None: 
            acc_data = self.get_acc_data(acc_id) 

            if acc_data: 
                name = acc_data['name'] 
                username = acc_data['username'] 

                if name == str(m.author): 
                    data = {
                        'user_id': m.author.id, 
                        'acc_id': acc_id, 
                    } 

                    self.links_table.upsert(data, ['user_id'], ensure=True) 

                    await self.send(c, content=f"Successfully linked to Deeeep.io account with username `{username}` and ID `{acc_id}`. \
You can change the account's name back now. ", reference=m) 
                else: 
                    await self.send(c, content=f"You must set your Deeeep.io account's name to your discord tag (`{m.author!s}`) when linking. \
You only need to do this when linking; you can change it back afterward. Read <{self.LINK_HELP_IMG}> for more info. ", reference=m) 
            else: 
                return True
        else: 
            return True
    
    @command('link', definite_usages={
        (): 'View help on linking accounts', 
        ('<account_ID>',): 'Link Deeeep.io account with ID `<account_ID>` to your account', 
        ('<account_profile_pic_URL>',): "Like above, but with the URL of the account's profile picture", 
    }) 
    async def link(self, c, m, query=None): 
        if query: 
            return await self.link_dep_acc(c, m, query) 
        else: 
            await self.link_help(c, m) 
    
    @command('unlink', definite_usages={
        (): 'Unlink your Deeeep.io account', 
    })
    async def unlink(self, c, m): 
        self.links_table.delete(user_id=m.author.id) 

        await self.send(c, content='Unlinked your account. ', reference=m) 
    
    @command('statstest', definite_usages={
        ('<account_ID>',): 'View Deeeep.io account with ID `<account_ID>`', 
        ('<account_profile_pic_URL>',): "Like above, but with the URL of the account's profile picture", 
    }, public=False) 
    @requires_owner
    async def cheat_stats(self, c, m, query): 
        acc_id = self.get_acc_id(query) 
        
        if acc_id is not None: 
            await self.send(c, embed=self.acc_embed(acc_id)) 
        else: 
            return True
    
    @command('prefix', definite_usages={
        ('<prefix>',): "Set the server-wide prefix for this bot to `<prefix>`", 
        (PREFIX_SENTINEL,): f'Reset the server prefix to the default, `{DEFAULT_PREFIX}`', 
    }) 
    @requires_perms(req_one=('manage_messages', 'manage_roles')) 
    async def set_prefix(self, c, m, prefix): 
        if prefix == self.PREFIX_SENTINEL: 
            self.prefixes_table.delete(guild_id=c.guild.id) 

            await self.send(c, content=f'Reset to default prefix `{self.DEFAULT_PREFIX}`') 
        else: 
            if len(prefix) <= self.MAX_PREFIX: 
                data = {
                    'guild_id': c.guild.id, 
                    'prefix': prefix, 
                } 

                self.prefixes_table.upsert(data, ['guild_id'], ensure=True) 

                await self.send(c, content=f'Custom prefix is now `{prefix}`. ') 
            else: 
                await self.send(c, content=f'Prefix must not exceed {self.MAX_PREFIX} characters. ', reference=m) 
    
    @command('revc', definite_usages={
        ('<channel>',): "Sets `<channel>` as the logging channel for skn review", 
        (): 'Like above, but with the current channel', 
        (REV_CHANNEL_SENTINEL,): 'Un-set the logging channel', 
    }, public=False) 
    @requires_owner
    async def set_rev_channel(self, c, m, flag=None): 
        if flag == self.REV_CHANNEL_SENTINEL: 
            self.rev_data_table.delete(key=self.REV_CHANNEL_KEY) 

            await self.send(c, content="Channel removed as the logging channel.") 
        else: 
            if flag is None: 
                channel_id = c.id
            else: 
                channel_id = self.decode_channel(c, flag) 
            
            if channel_id is not None: 
                data = {
                    'key': self.REV_CHANNEL_KEY, 
                    'channel_id': channel_id, 
                } 

                self.rev_data_table.upsert(data, ['key'], ensure=True) 

                await self.send(c, content=f'Set <#{channel_id}> as the logging channel for skin review.') 
            else: 
                return True

    @command('revi', definite_usages={
        ('<i>',): 'Does something', 
    }, public=False) 
    @requires_owner
    async def set_rev_interval(self, c, m, interval): 
        if interval.isnumeric(): 
            seconds = int(interval) 

            data = {
                'key': self.REV_INTERVAL_KEY, 
                'interval': seconds, 
            } 

            self.rev_data_table.upsert(data, ['key'], ensure=True) 

            await self.send(c, content=f'Set interval to {seconds} seconds. ') 
        else: 
            return True
    
    @command('sbchannel', definite_usages={
        ('add', '<channel>'): 'Adds `<channel>` as a Skin Board channel', 
        ('add',): 'Like above, but with the current channel', 
        ('remove', '<channel>'): 'Removes `<channel>` as a Skin Board channel', 
        ('remove',): 'Like above, but with the current channel', 
    }, public=False) 
    @requires_owner
    async def set_sb_channels(self, c, m, flag, channel=None): 
        flag = flag.lower() 

        if channel: 
            channel_id = self.decode_channel(c, channel) 
        else: 
            channel_id = c.id
        
        if channel_id is not None: 
            if flag == 'remove': 
                self.sb_channels_table.delete(channel_id=channel_id) 

                await self.send(c, content=f"<#{channel_id}> removed as a Skin Board channel.") 
            elif flag == 'add': 
                data = {
                    'channel_id': channel_id, 
                } 

                self.sb_channels_table.upsert(data, ['channel_id'], ensure=True) 

                await self.send(c, content=f'Added <#{channel_id}> as a Skin Board channel.') 
            else: 
                return True
        else: 
            return True
    
    PENDING_FILTERS = {
        'reskin': lambda skin: skin['parent'], 
        'halloween': lambda skin: skin['season'] == 'hallooween', 
        'christmas': lambda skin: skin['season'] == 'christmas', 
        'valentines': lambda skin: skin['season'] == 'valentines', 
        'easter': lambda skin: skin['season'] == 'easter', 
    } 

    FILTERS_STR = tools.format_iterable(PENDING_FILTERS.keys(), formatter='`{}`') 
    
    @command('pending', indefinite_usages={
        ('<filters>',): f'Get a list of all pending skins in Creators Center that match the filter(s). Valid filters are {FILTERS_STR}.', 
    }) 
    @requires_sb_channel
    async def pending_search(self, c, m, *filter_strs): 
        filters = set() 
        filter_strs = set(map(str.lower, filter_strs)) 

        for lowered in filter_strs: 
            if lowered in self.PENDING_FILTERS: 
                skin_filter = self.PENDING_FILTERS[lowered] 

                filters.add(skin_filter) 
            else: 
                return True
        
        await self.send(c, embed=self.pending_embed(filter_strs, filters)) 
    
    @command('shutdown', definite_usages={
        (): "Turn off the bot", 
    }, public=False) 
    @requires_owner
    async def shut_down(self, c, m): 
        await self.send(c, content='shutting down') 

        self.logging_out = True

        await self.change_presence(status=discord.Status.dnd, activity=discord.Game(name='shutting down')) 
    
    @command('help', definite_usages={
        (): 'Get a list of all public commands', 
        ('<command>',): 'Get help on `<command>`', 
    }) 
    async def send_help(self, c, m, command_name=None): 
        if command_name: 
            comm = commands.Command.get_command(command_name)  

            if comm: 
                usage_str = comm.usages_str(self, c, m) 

                await self.send(c, content=f'''How to use the `{command_name}` command: 

{usage_str}''') 
            else: 
                prefix = self.prefix(c) 

                await self.send(c, content=f"That's not a valid command name. Type `{prefix}{self.send_help.name}` for a list of public commands. ", reference=m) 
        else: 
            com_list_str = tools.format_iterable(commands.Command.all_commands(public_only=True), formatter='`{}`') 
            prefix = self.prefix(c) 

            await self.send(c, content=f'''All public commands for this bot: {com_list_str}. 
Type `{prefix}{self.send_help.name} <command>` for help on a specified `<command>`''') 
    
    @command('info', definite_usages={
        (): 'Display info about this bot', 
    }) 
    async def send_info(self, c, m): 
        await self.send(c, embed=await self.self_embed(c)) 
    
    @task
    async def execute(self, comm, c, m, *args): 
        message_time_str = m.created_at.strftime(self.MESSAGE_LOG_TIME_FORMAT) 

        message_str = f'''Message content: {m.content}
Message author: {m.author}
Message channel: {c}
Message guild: {m.guild}
Message time: {message_time_str}''' 

        debug(message_str)  

        permissions = c.permissions_for(c.guild.me) 

        if permissions.send_messages: 
            await comm.attempt_run(self, c, m, *args) 
        else: 
            await self.send(m.author, f"I can't send messages in {c.mention}! ")
    
    async def handle_command(self, m, c, prefix, words): 
        command, *args = words
        command = command[len(prefix):] 

        comm = commands.Command.get_command(command) 

        if comm: 
            await self.execute(comm, c, m, *args) 
    
    async def on_message(self, msg): 
        c = msg.channel

        if hasattr(c, 'guild'): 
            prefix = self.prefix(c) 
            words = msg.content.split(' ') 

            if len(words) >= 1 and words[0].startswith(prefix): 
                await self.handle_command(msg, c, prefix, words) 