# from info import *
# from telebot.util import user_link
# from telebot.formatting import escape_html
# from imysdb import IMYDB

# db = IMYDB('feds/federation.json')

# async def is_user_admin(chat_id, user_id):
#     admin = await bot.get_chat_member(chat_id, user_id)
#     return admin.status in ['administrator', 'creator']

# async def create_federation(m):
#     if not await is_user_admin(m.chat.id, m.from_user.id):
#         return 'You must be an admin in this group to create a federation.'
    
#     args = m.text.split()
#     if len(args) < 2:
#         return 'Usage: /create_federation <name>'
#     name = args[1]
#     chat_id = m.chat.id
#     federations = db.get('federations', {})
#     if name in federations:
#         return f'Federation {name} already exists.'
#     else:
#         federations[name] = {
#             'groups': [],
#             'banned_users': [],
#             'admins': [m.from_user.id],
#             'creator': m.from_user.id
#         }
#         db.set('federations', federations)
#         return f'Federation {name} created by {user_link(m.from_user)}.'

# async def join_federation(m):
#     if not await is_user_admin(m.chat.id, m.from_user.id):
#         return 'You must be an admin in this group to join a federation.'
    
#     args = m.text.split()
#     if len(args) < 2:
#         return 'Usage: /join_federation <name>'
#     federation_name = args[1]
#     chat_id = m.chat.id
#     federations = db.get('federations', {})
#     if federation_name in federations:
#         if chat_id not in federations[federation_name]['groups']:
#             federations[federation_name]['groups'].append(chat_id)
#             db.set('federations', federations)
#             return f'Group joined federation {federation_name}.'
#         else:
#             return f'Group is already in federation {federation_name}.'
#     else:
#         return f'Federation {federation_name} not found.'

# async def leave_federation(m):
#     if not await is_user_admin(m.chat.id, m.from_user.id):
#         return 'You must be an admin in this group to leave a federation.'
    
#     args = m.text.split()
#     if len(args) < 2:
#         return 'Usage: /leave_federation <name>'
#     federation_name = args[1]
#     chat_id = m.chat.id
#     federations = db.get('federations', {})
#     if federation_name in federations:
#         if chat_id in federations[federation_name]['groups']:
#             federations[federation_name]['groups'].remove(chat_id)
#             db.set('federations', federations)
#             return f'Group left federation {federation_name}.'
#         else:
#             return f'Group is not in federation {federation_name}.'
#     else:
#         return f'Federation {federation_name} not found.'

# def list_federations():
#     federations = db.get('federations', {})
#     if not federations:
#         return 'No federations available.'
#     federation_list = '\n'.join(federations.keys())
#     return f'Available federations:\n{federation_list}'

# async def fban(m):
#     if not await is_user_admin(m.chat.id, m.from_user.id):
#         return 'You must be an admin in this group to ban a user.'
    
#     if not m.reply_to_message:
#         return 'Usage: /fban (reply to a user message)'
#     user_id = m.reply_to_message.from_user.id
#     chat_id = m.chat.id
#     federations = db.get('federations', {})
#     for federation_name, federation_data in federations.items():
#         if chat_id in federation_data['groups']:
#             if m.from_user.id in federation_data['admins']:
#                 if user_id not in federation_data['banned_users']:
#                     federation_data['banned_users'].append(user_id)
#                     db.set('federations', federations)
#                     # Propagate ban to all groups in the federation
#                     for group_id in federation_data['groups']:
#                         await bot.ban_chat_member(group_id, user_id)
#                     return f'User {user_link(m.reply_to_message.from_user)} banned in federation {federation_name}.'
#                 else:
#                     return f'User {user_link(m.reply_to_message.from_user)} is already banned in federation {federation_name}.'
#             else:
#                 return f'You are not an admin in federation {federation_name}.'
#     return 'This group is not part of any federation.'

# async def funban(m):
#     if not await is_user_admin(m.chat.id, m.from_user.id):
#         return 'You must be an admin in this group to unban a user.'
    
#     if not m.reply_to_message:
#         return 'Usage: /funban (reply to a user message)'
#     user_id = m.reply_to_message.from_user.id
#     chat_id = m.chat.id
#     federations = db.get('federations', {})
#     for federation_name, federation_data in federations.items():
#         if chat_id in federation_data['groups']:
#             if m.from_user.id in federation_data['admins']:
#                 if user_id in federation_data['banned_users']:
#                     federation_data['banned_users'].remove(user_id)
#                     db.set('federations', federations)
#                     # Propagate unban to all groups in the federation
#                     for group_id in federation_data['groups']:
#                         await bot.unban_chat_member(group_id, user_id)
#                     return f'User {user_link(m.reply_to_message.from_user)} unbanned in federation {federation_name}.'
#                 else:
#                     return f'User {user_link(m.reply_to_message.from_user)} is not banned in federation {federation_name}.'
#             else:
#                 return f'You are not an admin in federation {federation_name}.'
#     return 'This group is not part of any federation.'

# async def check_and_ban_user(m):
#     user_id = m.from_user.id
#     chat_id = m.chat.id
#     federations = db.get('federations', {})
#     for federation_name, federation_data in federations.items():
#         if chat_id in federation_data['groups']:
#             if user_id in federation_data['banned_users']:
#                 info = await bot.get_me()
#                 me = await bot.get_chat_member(chat_id, info.id)
#                 if me.status in ['administrator', 'creator']:
#                     if me.can_restrict_members:
#                         await bot.ban_chat_member(chat_id, user_id)
#                         return f'User {user_link(m.from_user)} banned in chat {chat_id} as they are fbanned in federation {federation_name}.'
#                     else:
#                         return f'Bot does not have permission to ban users in chat {chat_id}.'
#                 else:
#                     return f'Bot is not an admin in chat {chat_id}.'

# async def promote_fed_admin(m):
#     if not await is_user_admin(m.chat.id, m.from_user.id):
#         return 'You must be an admin in this group to promote a federation admin.'
    
#     user_id = m.reply_to_message.from_user.id
#     args = m.text.split()
#     if len(args) < 2:
#         return 'Usage: /fpromote <federation_name>'
#     federation_name = args[1]
#     federations = db.get('federations', {})
#     if federation_name in federations:
#         if m.from_user.id in federations[federation_name]['admins']:
#             if user_id not in federations[federation_name]['admins']:
#                 federations[federation_name]['admins'].append(user_id)
#                 db.set('federations', federations)
#                 return f'User {escape_html(user_link(m.reply_to_message.from_user))} promoted to admin in federation {escape_html(federation_name)}.'
#             else:
#                 return f'User {escape_html(user_link(m.reply_to_message.from_user))} is already an admin in federation {escape_html(federation_name)}.'
#         else:
#             return f'You are not an admin in federation {escape_html(federation_name)}.'
#     else:
#         return f'Federation {escape_html(federation_name)} not found.'

# async def demote_fed_admin(m):
#     if not await is_user_admin(m.chat.id, m.from_user.id):
#         return 'You must be an admin in this group to demote a federation admin.'
    
#     user_id = m.reply_to_message.from_user.id
#     args = m.text.split()
#     if len(args) < 2:
#         return 'Usage: /depromote_fed_admin <federation_name> <user_id>'
#     federation_name = args[1]
#     federations = db.get('federations', {})
#     if federation_name in federations:
#         if m.from_user.id in federations[federation_name]['admins']:
#             if user_id in federations[federation_name]['admins']:
#                 federations[federation_name]['admins'].remove(user_id)
#                 db.set('federations', federations)
#                 return f'User {user_link(m.reply_to_message.from_user)} demoted from admin in federation {federation_name}.'
#             else:
#                 return f'User {user_link(m.reply_to_message.from_user)} is not an admin in federation {federation_name}.'
#         else:
#             return f'You are not an admin in federation {federation_name}.'
#     else:
#         return f'Federation {federation_name} not found.'

# async def delete_federation(m):
#     if not await is_user_admin(m.chat.id, m.from_user.id):
#         return 'You must be an admin in this group to delete a federation.'
    
#     args = m.text.split()
#     if len(args) < 2:
#         return 'Usage: /delfed <fed name>'
#     federation_name = args[1]
#     federations = db.get('federations', {})
#     if federation_name in federations:
#         federation_data = federations[federation_name]
#         if m.from_user.id == federation_data['creator']:
#             del federations[federation_name]
#             db.set('federations', federations)
#             return f'Federation {federation_name} has been deleted.'
#         else:
#             return f'You are not the creator of federation {federation_name}.'
#     else:
#         return f'Federation {federation_name} not found.'