import os

path_config = 'c:/Users/Maksym/Desktop/discordUA05/config.py'

# 1. Складаємо ідеальний список ролей (адмінські та інші дозволені)
# Використовую список із запитів користувача, враховуючи capitalization
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

# Видаляємо дублікати та сортуємо (але зберігаємо адмінські на початку якщо треба, хоча sort ок)
fixed_roles = sorted(list(set(fixed_roles)))

with open(path_config, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
in_mute_roles = False
mute_roles_added = False

for line in lines:
    if 'MUTE_ROLES = [' in line:
        in_mute_roles = True
        continue
    
    if in_mute_roles:
        if ']' in line:
            # Check if this is the REAL end of MUTE_ROLES or just one of the broken lines
            # If the next line contains more strings, it's the broken part
            in_mute_roles = False
            if not mute_roles_added:
                new_lines.append('MUTE_ROLES = [\n')
                for i in range(0, len(fixed_roles), 3):
                    chunk = fixed_roles[i:i+3]
                    new_lines.append(f'    {", ".join(f"\"{r}\"" for r in chunk)},\n')
                new_lines.append(']\n')
                mute_roles_added = True
            continue
        else:
            continue # skip lines inside the old MUTE_ROLES
            
    # Also skip the garbage lines that look like "Role", "Role"
    if not in_mute_roles and line.strip().startswith('"') and line.strip().endswith('",'):
        continue
    if not in_mute_roles and line.strip() == ']':
        continue
        
    new_lines.append(line)

with open(path_config, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('FIXED_CONFIG')
