import json
import os

path_json = 'c:/Users/Maksym/Desktop/discordUA05/guilds_config.json'
path_config = 'c:/Users/Maksym/Desktop/discordUA05/config.py'

# 1. Складаємо ідеальний список ролей
fixed_roles = [
    'Головний Адміністратор', 'Заступник Головного Адміністратора', 'Куратор Адміністрації',
    'Куратор Слідкуючої Адміністрації', 'Куратор Організації', 'Куратор Держ.', 'Куратор Неоф',
    'Слідкуючий Адміністрації', 'Старший Адміністратор', 'Куратор Скарг', 'Івент-Менеджер',
    'ГС Міністерств', 'ЗГС Міністерств', 'Слідкуючий МВС', 'Слідкуючий МВП', 'Слідкуючий МО',
    'Слідкуючий МОЗ', 'Слідкуючий Неоф', 'Адміністрація Серверу',
    'Аудитор сервера', 'ГС ДО', 'ЗГС ДО', 'ГС НО', 'ЗГС НО', 'ГС ЦС', 'ЗГС ЦС',
    'ГС МВС', 'ЗГС МВС', 'ГС МО', 'ЗГС МО', 'Куратор Заходів', 'Старший адміністратор',
    'Адміністратор', 'Ivent Manager', 'Старший Модератор', 'Модератор', 'Молодший Модератор',
    'Старший Слідкуючий Нелегальних організацій', 'Слідкуючий', 'Слідкуючий Нелегальних організацій',
    'Адміністрація серверу', 'Модератор (Discord)', '[А] Модератор', 'Старший модератор (Discord)',
    'Куратор Модерації (Discord)', 'Заступник ГМ (Discord)', 'Головний Модератор (Discord)',
    'Спеціальний модератор (Discord)', '[А] Молодший модератор',
    'Керівництво проєкту', 'Команда проєкту', 'Спеціальний Адміністратор', 'Технічний Адміністратор',
    'Куратор Держ', "Куратор Сім'ї", '[ЗГА] Заступник ГА', '[КА] Куратор Адміністрації',
    'ГА | Головний Адміністратор', 'КА | Куратор Адміністрації', 'КМА | Куратор молодшої Адміністрації',
    '[КМА] Куратор молодшої адміністрації', '[К]Куратор державних Організацій',
    '[К] Куратор Нелегальних Організацій', 'Куратор структури', '[А] Адміністратор',
    'Стажер (Discord)', 'Куратор Структури', 'К | Куратор Нелегалів',
    'К | Куратор Державних Організацій', 'Ведучий заходів (Discord)',
    'ТЦК та СП', 'ТСН', 'ЗСУ', 'НПУ м. Київ', 'НПУ м. Дніпро', 'НПУ м. Львів',
    'СБУ м. Київ', 'СБУ м. Дніпро', 'СБУ м. Львів'
]

# 2. Очищення JSON
with open(path_json, 'r', encoding='utf-8') as f:
    config_data = json.load(f)

def is_valid(role):
    role = role.strip()
    if not role or len(role) <= 2: return False
    # Видаляємо ролі, що закінчуються на пробіл або мають дивні залишки
    if role.endswith(' '): return False
    # Якщо роль в нашому "ідеальному" списку - вона точно ок
    if role in fixed_roles: return True
    # Якщо роль починається з великої літери і не виглядає як сміття
    if role[0].isupper() or role.startswith('['):
        # Додаткові перевірки на фрагменти слів
        fragments = ['іністерств', 'елегальних', 'еоф', 'дміністрації', 'одератор', 'дміністратор']
        if any(f in role for f in fragments) and not any(role == c for c in fixed_roles):
            # Перевіряємо чи це не одна з початкових некоректних ролей
            if role[0].islower(): return False
        return True
    return False

for gid in config_data:
    current = config_data[gid].get('allowed_roles', [])
    cleaned = set()
    for r in current:
        r_strip = r.strip()
        if is_valid(r_strip):
            cleaned.add(r_strip)
    cleaned.update(fixed_roles)
    config_data[gid]['allowed_roles'] = sorted(list(cleaned))

with open(path_json, 'w', encoding='utf-8') as f:
    json.dump(config_data, f, ensure_ascii=False, indent=4)

# 3. Очищення config.py
# Просто перезапишемо MUTE_ROLES ідеальним списком для порядку
with open(path_config, 'r', encoding='utf-8') as f:
    config_lines = f.readlines()

new_config_lines = []
skip = False
for line in config_lines:
    if 'MUTE_ROLES = [' in line:
        new_config_lines.append('MUTE_ROLES = [\n')
        # Групуємо ролі по 3 для краси
        for i in range(0, len(fixed_roles), 3):
            chunk = fixed_roles[i:i+3]
            roles_str = ', '.join(f'"{r}"' for r in chunk)
            if i + 3 < len(fixed_roles):
                new_config_lines.append(f'    {roles_str},\n')
            else:
                new_config_lines.append(f'    {roles_str}\n')
        new_config_lines.append(']\n')
        skip = True
    elif skip and ']' in line:
        skip = False
        continue
    elif not skip:
        new_config_lines.append(line)

with open(path_config, 'w', encoding='utf-8') as f:
    f.writelines(new_config_lines)

print('FINAL_SUCCESS')
