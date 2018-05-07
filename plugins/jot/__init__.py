import irc3, shelve, re
from irc3.plugins.cron import cron
from random import choice

@irc3.plugin
class Plugin:

    def __init__(self, bot):
        self.bot = bot
        self.jotfile = self.bot.config.get('jot', {}).get('jotfile','.jots')
        self.controlchar = self.bot.config.get('jot', {}).get('controlchar','>')
        
        self.features = {
            'add':    ['(?P<key>[\w\s]+?)(?P<global>\s*-g)?\s*=\s*(?P<data>.*)',   self.jot_add,    ['key', 'data', 'global']],
            'also':   ['(?P<key>[\w\s]+?)(?P<global>\s*-g)?\s*\|=\s*(?P<data>.*)', self.jot_also,   ['key', 'data', 'global']],
            'get':    ['(?P<key>[\w\s]+?)(?P<global>\s*-g)?\s*',                   self.jot_get,    ['key', 'global']        ],
            'tell':   ['(?P<key>[\w\s]+?)(?P<global>\s*-g)?\s*@\s*(?P<at>\S+)\s*', self.jot_get,    ['key', 'global', 'at']  ],
            'search': ['\?(?P<key>[\w\s]+?)\s*',                                   self.jot_search, ['key']                  ],
            'remove': ['-(?P<key>[\w\s]+?)(?P<global>\s*-g)?',                     self.jot_remove, ['key', 'global']        ]
        }
        # compile feature regexps
        for feature in self.features:
            self.features[feature][0] = re.compile('^'+self.controlchar+self.features[feature][0]+'$')
        
        self.jotfile_upgrade()
        self.jot_load()
        print("JOT ~ LOADED")
    
    # ** Upgrade jotfile if needed
    def jotfile_upgrade(self):
        with shelve.open(self.jotfile) as channels:
            if 'g#l#o#b#a#l' in channels:
                beep = channels['g#l#o#b#a#l']
                del channels['g#l#o#b#a#l']
                channels[''] = beep
            
    # --- Features
    
    def jot_add(self, nick, target, key, data, globl=None):
        if globl is not None and nick in list(self.bot.channels[target].modes['@']):
            target = ''
        if not self.jot_exists(key, target):
            self.jot_write(key, {'key':key, 'from':nick, 'value':[data]}, target)
            self.bot.privmsg(nick, 'Ok.')
        else:
            self.bot.privmsg(nick, "The key '"+key+"' already exists.")
    
    def jot_also(self, nick, target, key, data, globl=None):
        if globl is not None and nick in list(self.bot.channels[target].modes['@']):
            target = ''
        if self.jot_exists(key, target):
            result = self.jot_read(key, target)
            result['value'].append(data)
            self.jot_write(key, result, target)
            self.bot.privmsg(nick, 'Ok.')
        else:
            self.jot_add(nick, target, key, data, globl)
            
    def jot_get(self, nick, target, key, globl=None, at=None):
        if self.jot_exists(key, target) and globl is None:
            jot = self.jot_read(key, target)
            nick = at if at is not None else nick
            self.bot.privmsg(target, nick + ": " + choice(jot['value']))
            return
        if self.jot_exists(key, ''):
            jot = self.jot_read(key, '')
            nick = at if at is not None else nick
            self.bot.privmsg(target, nick + ": " + choice(jot['value']))
            
    def jot_search(self, nick, target, key):
        result = "Results "
        count = 0
        if target in self.jots:
            for k in self.jots[target]:
                if key.lower() in k:
                    result = result + " " + self.controlchar + k + " "
                    count+=1
        for k in self.jots['']:
            if key.lower() in k:
                result = result + " " + self.controlchar + K + " "
        self.bot.privmsg(target, nick + ": " + str(count) + " " + result)
    
    def jot_remove(self, nick, target, key, globl=None):
        if nick in list(self.bot.channels[target].modes['@']):
            if globl is not None:
                target = ''
            key = key.lower()
            if target in self.jots:
                if key in self.jots[target]:
                    del self.jots[target][key]
                    self.bot.privmsg(nick, 'Ok.')
                    
    # --- Reload & Accessors
                    
    @classmethod
    def reload(cls, old):
        return cls(old.bot)
    
    def jot_load(self):
        self.jots = {}
        with shelve.open(self.jotfile) as channels:
            for channel in channels:
                self.jots[channel] = channels[channel]
        if '' not in self.jots:
            self.jots[''] = {}

    @cron('*/5 * * * *')
    def jot_save(self):
        with shelve.open(self.jotfile) as channels:
            for channel in self.jots:
                channels[channel] = self.jots[channel]
        print ("JOTFILE SAVED")
    
    def jot_read(self, key, channel):
        key = key.lower()
        if channel in self.jots:
            if key in self.jots[channel]:
                return self.jots[channel][key]
        return None
    
    def jot_write(self, key, value, channel):
        if channel not in self.jots:
            self.jots[channel] = {}
        result = not self.jot_exists(key, channel)
        self.jots[channel][key.lower()] = value
        return result
    
    def jot_exists(self, key, channel):
        return (channel in self.jots) and (key.lower() in self.jots[channel])
        
    # ---  Core    
        
    @irc3.event('^(@\S+ )?:(?P<nick>\S+)!\S+@\S+ PRIVMSG (?P<target>\S+) :(?P<data>.*)$')
    def jot_core(self, nick, target, data, **kw):
        if (self.bot.obeying_commands(target)):
            for name in self.features:
                (pattern, func, args) = self.features[name]
                result = pattern.match(data)
                if result:
                    arglist = []
                    for arg in args:
                        arglist.append(result.group(arg))
                    func(nick, target, *arglist)

