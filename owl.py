# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 caveman (https://github.com/al-caveman/owl)
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

#
# Introduction
#
# The indispensable weechat survival tool against the preying staffers. In many
# cases, such staffers are not even ops. So simply looking for people with "@"
# prefixes will mislead you.
# 
# "The silent dog is more dangerous than the barking one." -- caveman, 2019
# 
# owl allows for colorizing the input field depending on whether there are
# hunters lurking in the background in the current buffer, as well as letting
# you list them in the buffer.
#
#
# How does it work?  See `/help owl`
#

#
# History:
#
# 2019-09-03, caveman:
#     v0: initial version

import_ok = True
import re
import sys
try:
    import weechat
except ImportError:
    print('This script must be run under WeeChat.')
    print('Get WeeChat now at: http://www.weechat.org/')
    import_ok = False

SCRIPT_NAME = 'owl'
SCRIPT_AUTHOR = 'caveman <toraboracaveman@protonmail.com>'
SCRIPT_VERSION = '0'
SCRIPT_LICENSE = 'GPL3'
SCRIPT_DESC = 'Warns you of silent dogs, such as preying network staffers.'

SCRIPT_COMMAND = 'owl'
SCRIPT_ARGS_DESC= """
list [[[BUFFER_NAME] BUFFER_NAME] ... BUFFER_NAME]
    Shows the list of matched nicks in BUFFER_NAME.

enable [[[BUFFER_NAME] BUFFER_NAME] ... BUFFER_NAME]
    Interactively enables owl in BUFFER_NAME.  For permanent settings, assign
    values to variables in /set owl.

disalbe [[[BUFFER_NAME] BUFFER_NAME] ... BUFFER_NAME]
    Interactively disables owl in BUFFER_NAME.  For permanent settings, assign
    values to variables in /set owl.

BUFFER_NAME
    [[network.]#channel], e.g. full buffer name, such as "freenode.#weechat",
    or partial, such as "#weechat" or nothing (i.e. "").
    
    If "network." is not specified, it will default to the server name of the
    buffer where the command "/owl ..." is executed.  E.g. if "/owl enable
    #weechat" is executed in a buffer falling under the server "freenode", then
    "/owl enable #weechat" will be equivalent to "/owl enable
    freenode.#weechat".
    
    If nothing is given, at all, and "/owl enable" is typed in the input of he
    buffer "freenode.#weechat", then "/owl enable" will be equivalent to "/owl
    enable freenode.#weechat".

For bugs and feature requests: https://github.com/al-caveman/owl/issues
"""

DEBUG = True
DIR_IN = 0
DIR_OUT = 1
RULES = 3
RE_USERHOST = re.compile(
    r'.+ :(?P<nick>\S+?)\*?=(\+|\-)(?P<user>\S+?)@(?P<host>\S+)'
)

# script options
owl_settings_default = {
    'rule_1_match': (
        '.*!~.*@.*staff.*',
        'python regular expression to match on hostnames for rule 1.'),
    'rule_1_input_bg_on': (
        '/set weechat.bar.input.color_bg red',
        'background color of input bar when owl spotted stuff in the buffer.'),
    'rule_1_input_bg_off': (
        '/unset weechat.bar.input.color_bg',
        'background color of input bar when owl spots nothing there in the buffer.'),
    'rule_1_input_fg_on': (
        '/set weechat.bar.input.color_fg white',
        'foreground color of input bar when owl spotted stuff in the buffer.'),
    'rule_1_input_fg_off': (
        '/unset weechat.bar.input.color_fg',
        'Foreground color of input bar when owl spots nothing there in the buffer.'),

    'rule_2_match': (
        '',
        'python regular expression to match on hostnames for rule 1.'),
    'rule_2_input_bg_on': (
        '',
        'background color of input bar when owl spotted stuff in the buffer.'),
    'rule_2_input_bg_off': (
        '',
        'background color of input bar when owl spots nothing there in the buffer.'),
    'rule_2_input_fg_on': (
        '',
        'foreground color of input bar when owl spotted stuff in the buffer.'),
    'rule_2_input_fg_off': (
        '',
        'Foreground color of input bar when owl spots nothing there in the buffer.'),

    'rule_3_match': (
        '',
        'python regular expression to match on hostnames for rule 1.'),
    'rule_3_input_bg_on': (
        '',
        'background color of input bar when owl spotted stuff in the buffer.'),
    'rule_3_input_bg_off': (
        '',
        'background color of input bar when owl spots nothing there in the buffer.'),
    'rule_3_input_fg_on': (
        '',
        'foreground color of input bar when owl spotted stuff in the buffer.'),
    'rule_3_input_fg_off': (
        '',
        'Foreground color of input bar when owl spots nothing there in the buffer.'),

    'buffers_on': (
        '',
        'comma separated list of buffer names, e.g. freenode.#chan,dalnet.#chan2, where owl is active.'),
    'buffers_off': (
        '',
        'comma separated list of buffer names, e.g. freenode.#chan,dalnet.#chan2, where owl is inactive.'),
    'channels_default': (
        'on',
        'whether owl is active by default.  either "on" or "off".'),
    'input_bg_default': (
        '/set weechat.bar.input.color_bg default',
        'default background colour for input line when no owl alert is there.'),
    'input_fg_default': (
        '/set weechat.bar.input.color_fg default',
        'default foreground colour for input line when no owl alert is there.'),
    'userhost_timeout': (
        '300',
        'how long to wait to get userhost responses from server.'),
}

# global variables 
owl_settings = {}
owl_state = {
    'nick_buffs' : {},
    'buff_alerts' : {},
    'last_buff' : None,
    'settings_changed':  False,
}
owl_on_buffers = set()
owl_off_buffers = set()
owl_default_on = False
owl_match = {}
owl_action = {}

def optimize_configs():
    global owl_default_on
    for rule in range(1, RULES+1):
        if len(owl_settings['rule_{}_match'.format(rule)]):
            owl_match[rule] = re.compile(owl_settings['rule_{}_match'.format(rule)])
            owl_action[rule] = {
                'rule_input_bg_on'  : owl_settings['rule_{}_input_bg_on'.format(rule)],
                'rule_input_bg_off' : owl_settings['rule_{}_input_bg_off'.format(rule)],
                'rule_input_fg_on'  : owl_settings['rule_{}_input_fg_on'.format(rule)],
                'rule_input_fg_off' : owl_settings['rule_{}_input_fg_off'.format(rule)],
            }
    if owl_settings['channels_default'] == 'on':
        owl_default_on = True
    owl_off_buffers.clear()
    owl_on_buffers.clear()
    for i in owl_settings['buffers_off'].split(','):
        owl_off_buffers.add(i)
    for i in owl_settings['buffers_on'].split(','):
        owl_on_buffers.add(i)

def owl_weechat_exec(cmd):
    if len(cmd):
        weechat.command('', cmd)

def owl_reset_input():
    owl_weechat_exec(owl_settings['input_bg_default'])
    owl_weechat_exec(owl_settings['input_fg_default'])
    return weechat.WEECHAT_RC_OK

def owl_buff_check(buff_ptr):
    # get buffer's name
    buff_name = weechat.buffer_get_string(buff_ptr, 'name')
    if DEBUG:
        weechat.prnt('', 'checking buffer: {}'.format(buff_name))
    # apply buffers' settings only if buffer has changed, or if settings
    # changed
    if (
        owl_state['last_buff'] == buff_name
        or owl_state['settings_changed'] == True
    ):
        if DEBUG:
            weechat.prnt('', '  buffer unchanged.  skipping..')
    else:
        owl_state['last_buff'] = buff_name
        owl_state['settings_changed'] = False
        owl_reset_input()
        if buff_name in owl_state['buff_alerts']:
            for rule in sorted(owl_state['buff_alerts'][buff_name]):
                owl_inputline_on(rule)

def owl_buff_switch(a,b,buff_cur_ptr):
    if DEBUG:
        weechat.prnt('', 'buff switch..')
    owl_buff_check(buff_cur_ptr)
    return weechat.WEECHAT_RC_OK

def owl_buff_current():
    if DEBUG:
        weechat.prnt('', 'buff current..')
    buff_cur_ptr = weechat.current_buffer()
    owl_buff_check(buff_cur_ptr)
    return weechat.WEECHAT_RC_OK

def owl_config_set():
    for option, value in owl_settings_default.items():
        if weechat.config_is_set_plugin(option):
            owl_settings[option] = weechat.config_get_plugin(option)
        else:
            weechat.config_set_plugin(option, value[0])
            weechat.config_set_desc_plugin(option, value[1])
            owl_settings[option] = value[0]

def owl_config_update(a,b,c):
    if DEBUG:
        weechat.prnt('', 'config updated')
    owl_state['settings_changed'] = True
    owl_config_set()
    optimize_configs()
    owl_buff_current()
    return weechat.WEECHAT_RC_OK

def owl_nick_added(a,b,c):
    weechat.prnt('', 'TEST:  {}-{}-{}'.format(a,b,c))
    buff_ptr, nick = c.split(',')
    buff_name = weechat.buffer_get_string(buff_ptr, 'name')
    if DEBUG:
        weechat.prnt(
            '', 'nick added:  {} in {}'.format(
                nick , buff_name
            )
        )
    owl_analyze(nick, user, host, buff_name, DIR_IN)
    return weechat.WEECHAT_RC_OK

def owl_nick_removed(a,b,c):
    weechat.prnt('', 'TEST:  {}-{}-{}'.format(a,b,c))
    buff_ptr, nick = c.split(',')
    buff_name = weechat.buffer_get_string(buff_ptr, 'name')
    if DEBUG:
        weechat.prnt(
            '', 'nick removed:  {} in {}'.format(
                nick , buff_name
            )
        )
    owl_analyze(nick, user, host, buff_name, DIR_OUT)
    return weechat.WEECHAT_RC_OK

def owl_nick_changed(a,b,c):
    if DEBUG:
        weechat.prnt('', 'nick changed..')
    owl_nick_removed(a,b,c)
    owl_nick_added(a,b,c)
    return weechat.WEECHAT_RC_OK

def owl_inputline_on(rule):
    owl_weechat_exec(owl_action[rule]['rule_input_bg_on'])
    owl_weechat_exec(owl_action[rule]['rule_input_fg_on'])

def owl_inputline_off(rule):
    owl_weechat_exec(owl_action[rule]['rule_input_bg_off'])
    owl_weechat_exec(owl_action[rule]['rule_input_fg_off'])

def owl_userhost_cb(a,b,c):
    rpl_userhost = c['output']
    if DEBUG:
        weechat.prnt(
            '',
            'RPL_USERHOST:  {}'.format(
                rpl_userhost
            )
        )
    m = RE_USERHOST.match(rpl_userhost)
    try:
        g = m.groupdict()
        nick = g['nick']
        user = g['user']
        host = g['host']
        buffs = []
        for buff_server in owl_state['nick_buffs']:
            if nick in owl_state['nick_buffs'][buff_server]:
                for buff_name in owl_state['nick_buffs'][buff_server][nick]:
                    buffs.append(buff_name)
                    owl_analyze(nick, user, host, buff_name, DIR_IN)
        if DEBUG:
            weechat.prnt('', '  nick:  {}'.format(nick))
            weechat.prnt('', '  user:  {}'.format(user))
            weechat.prnt('', '  host:  {}'.format(host))
            weechat.prnt('', '  buff:  {}'.format(buffs))
    except AttributeError as e:
        if DEBUG:
            weechat.prnt('', e)
    return weechat.WEECHAT_RC_OK

def owl_analyze(nick, user, host, buff_name, direction):
    nick_user_host = '{}!{}@{}'.format(nick, user, host)
    for rule in sorted(owl_match):
        if owl_match[rule].match(nick_user_host):
            if direction == DIR_IN:
                if buff_name in owl_state['buff_alerts']:
                    if rule in owl_state['buff_alerts'][buff_name]:
                        owl_state['buff_alerts'][buff_name][rule].add(nick_user_host)
                    else:
                        owl_state['buff_alerts'][buff_name][rule] = {nick_user_host}
                else:
                    owl_state['buff_alerts'][buff_name] = {rule: {nick_user_host}}
                owl_buff_current()
            elif direction == DIR_OUT:
                if buff_name in owl_state['buff_alerts']:
                    if rule in owl_state['buff_alerts'][buff_name]:
                        owl_state['buff_alerts'][buff_name][rule].remove(nick_user_host)
                if len(owl_state['buff_alerts'][buff_name][rule]) == 0:
                    del owl_state['buff_alerts'][buff_name][rule]
                owl_buff_current()
            else:
                weechat.prnt('',
                    'error code:  0xDEADBEEF.  '
                    'this is indeed a very strange error.  '
                    'developer couldn\'t even fathom that this might happen.  '
                    'but apparently he was wrong, as you can attest.  '
                    'plz submit an issue in https://github.com/al-caveman/owl.'
                )

def owl_init(buff_ptr):
    # get more info about this buffer
    buff_name = weechat.buffer_get_string(buff_ptr, 'name')
    buff_server = weechat.buffer_get_string(buff_ptr, 'localvar_server')
    buff_channel = weechat.buffer_get_string(buff_ptr, 'localvar_channel')
    if DEBUG:
        weechat.prnt('', 'ptr:{} name:{}\n'.format(buff_ptr, buff_name))

    # is owl active in this channel?
    if (
        buff_name in owl_on_buffers
        or (buff_name not in owl_off_buffers and owl_default_on)
    ):
        # analyze nicks in the buffer
        iln = weechat.infolist_get(
            'irc_nick', '', '{},{}'.format(buff_server, buff_channel)
        )
        while weechat.infolist_next(iln):
            nick_ptr = weechat.infolist_pointer(iln, 'pointer')
            nick = weechat.infolist_string(iln, 'name')
            user_host = weechat.infolist_string(iln, 'host')
            # should we use /userhost to get hostname?
            if len(user_host) == 0:
                # track nick-buffer relationship
                if buff_server in owl_state['nick_buffs']:
                    if nick in owl_state['nick_buffs'][buff_server]:
                        owl_state['nick_buffs'][buff_server][nick].append(buff_name)
                    else:
                        owl_state['nick_buffs'][buff_server][nick] = [buff_name]
                else:
                    owl_state['nick_buffs'][buff_server] = {
                        nick : [buff_name]
                    }
                # do hookie things
                weechat.hook_hsignal_send(
                    'irc_redirect_command',
                    {
                        'server': buff_server,
                        'pattern': 'userhost',
                        'signal': 'owl',
                        'string': nick,
                        'timeout': owl_settings['userhost_timeout'],
                    }
                )
                weechat.hook_signal_send(
                    'irc_input_send',
                    weechat.WEECHAT_HOOK_SIGNAL_STRING,
                    '{};;;;/userhost {}'.format(buff_server, nick)
                )
                user_host = '****PENDING****'
            else:
                user, host = user_host.split('@')
                owl_analyze(nick, user, host, buff_name, DIR_IN)
            if DEBUG:
                weechat.prnt( '', '  {}!{}\n'.format(nick, user_host))
        weechat.infolist_free(iln)

    return weechat.WEECHAT_RC_OK

def owl_cmd(a, buff_ptr, c):
    # parse args
    buff_name = weechat.buffer_get_string(buff_ptr, 'name')
    buff_server = weechat.buffer_get_string(buff_ptr, 'localvar_server') + '.'
    buff_channel = weechat.buffer_get_string(buff_ptr, 'localvar_channel')
    args = c.split()
    buff_names = []
    if len(args) > 1:
        for name in args[1:]:
            m = re.match(r'^(?P<server>(\S+\.)?)(?P<channel>(#\S+)?)$', name)
            tmp_server = buff_server
            tmp_channel = buff_channel
            if m:
                if len(m.groupdict()['server']):
                    tmp_server = m.groupdict()['server']
                if len(m.groupdict()['channel']):
                    tmp_channel = m.groupdict()['channel']
                tmp_buff_name = '{}{}'.format(tmp_server, tmp_channel)
            buff_names.append(tmp_buff_name)
    else:
            buff_names.append(buff_name)
    # do stuff
    if DEBUG:
        weechat.prnt('', 'cmd: {}-{}-{}'.format(a,buff_name,c))
        weechat.prnt('', '  server: {}'.format(buff_server))
        weechat.prnt('', '  channel: {}'.format(buff_channel))
        weechat.prnt('', '  subcommand: {}'.format(args[0]))
        weechat.prnt('', '  args: {}'.format(buff_names))
    if args[0] == 'list':
        nothing_found = True
        for b in buff_names:
            if b in owl_state['buff_alerts']:
                nothing_found = False
                weechat.prnt(
                    buff_ptr,
                    '{}owl found these dogs in {}:'.format(
                        weechat.prefix('action'),
                        b
                    )
                )
                for rule in owl_state['buff_alerts'][b]:
                    nicks = []
                    for i in sorted(owl_state['buff_alerts'][b][rule]):
                        nicks.append(i.split('!')[0])
                    weechat.prnt(
                        buff_ptr,
                        '{}rule {}:  {}'.format(
                            weechat.prefix('action'),
                            rule,
                            ' '.join(nicks)
                        )
                    )
        if nothing_found:
            weechat.prnt(
                buff_ptr,
                '{}{}'.format(
                    weechat.prefix('action'),
                    'owl found no dogs in:  {}'.format(' '.join(buff_names))
                )
            )
    elif args[0] == 'enable':
        pass
    elif args[0] == 'disable':
        pass
    else:
        weechat.prnt('', 'owl: unknown argument "{}"'.format(args[0]))
    return weechat.WEECHAT_RC_OK

if __name__ == '__main__' and import_ok:
    if weechat.register(SCRIPT_NAME, SCRIPT_AUTHOR, SCRIPT_VERSION,
                        SCRIPT_LICENSE, SCRIPT_DESC, '', ''):
        # initialize
        owl_config_set()
        optimize_configs()

        # register hooks
        weechat.hook_hsignal('irc_redirection_owl_userhost', 'owl_userhost_cb', '')
        weechat.hook_signal('buffer_switch', 'owl_buff_switch', '')
        weechat.hook_signal('nicklist_nick_added', 'owl_nick_added', '')
        weechat.hook_signal('nicklist_nick_changed', 'owl_nick_changed', '')
        weechat.hook_signal('nicklist_nick_removed', 'owl_nick_removed', '')
        weechat.hook_config('plugins.var.python.owl.*', 'owl_config_update', '')

        # check every buffer at start up
        ilb = weechat.infolist_get('buffer', '', '')
        while weechat.infolist_next(ilb):
            buff_ptr = weechat.infolist_pointer(ilb, 'pointer')
            owl_init(buff_ptr)
        weechat.infolist_free(ilb)

        # add command
        weechat.hook_command(
            SCRIPT_COMMAND,
            SCRIPT_DESC,
            '[list] | [enable|disable [server.channel|channel]]',
            SCRIPT_ARGS_DESC,
            'list'
            ' || enable %(filters_names)'
            ' || disable %(filters_names)',
            'owl_cmd',
            ''
        )
