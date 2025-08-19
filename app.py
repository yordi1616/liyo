from flask import Flask, render_template, request, redirect, url_for, make_response, session, flash
import json
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_very_secret_key_for_this_hamster_kombat_clone_game'

# --- Game Configuration ---
# Upgrades for 'Earn' page (per-tap profit)
TAP_UPGRADES = {
    'tap_upgrade_2': {'name': '+2 Tap', 'cost': 500, 'per_tap_bonus': 2},
    'tap_upgrade_3': {'name': '+3 Tap', 'cost': 700, 'per_tap_bonus': 3},
    'tap_upgrade_5': {'name': '+5 Tap', 'cost': 1200, 'per_tap_bonus': 5},
    'tap_upgrade_10': {'name': '+10 Tap', 'cost': 5000, 'per_tap_bonus': 10},
}

# Upgrades for 'Members' page (tap limit / energy)
LIMIT_UPGRADES = {
    'limit_upgrade_2000': {'name': 'Tap Limit +2000', 'cost': 500, 'bonus_limit': 2000},
    'limit_upgrade_3000': {'name': 'Tap Limit +3000', 'cost': 1000, 'bonus_limit': 3000},
    'limit_upgrade_4000': {'name': 'Tap Limit +4000', 'cost': 2000, 'bonus_limit': 4000},
    'limit_upgrade_5000': {'name': 'Tap Limit +5000', 'cost': 2500, 'bonus_limit': 5000},
}

DEFAULT_TAP_LIMIT = 1000 # Initial tap limit
TAP_REGEN_RATE_PER_SECOND = 1 # Taps regenerated per second

# --- Helper Functions for Cookie Management ---
def get_game_data(request):
    """Retrieves game data from cookie, or initializes it."""
    try:
        data = json.loads(request.cookies.get('game_data', '{}'))
    except json.JSONDecodeError:
        data = {} # If cookie is corrupted, reset it

    # Default values for new or corrupted data
    return {
        'username': data.get('username'),
        'score': data.get('score', 0),
        'last_visit': data.get('last_visit', datetime.now().isoformat()),
        'claimed_daily_bonus_date': data.get('claimed_daily_bonus_date', None),
        'per_tap_bonus': data.get('per_tap_bonus', 1), # Default 1 point per tap
        'current_tap_limit': data.get('current_tap_limit', DEFAULT_TAP_LIMIT),
        'taps_left': data.get('taps_left', DEFAULT_TAP_LIMIT),
        'task_completed': data.get('task_completed', False), # For 'akalewold' task
        'purchased_tap_upgrades': data.get('purchased_tap_upgrades', []), # List of IDs
        'purchased_limit_upgrades': data.get('purchased_limit_upgrades', []) # List of IDs
    }

def save_game_data(response, data):
    """Saves game data to cookie."""
    response.set_cookie('game_data', json.dumps(data))
    return response

def calculate_passive_income_and_regen_taps(game_data):
    """Calculates passive income (profit_per_hour not implemented yet, so no income for now)
       and regenerates taps based on time elapsed."""
    
    last_visit_time = datetime.fromisoformat(game_data['last_visit'])
    current_time = datetime.now()
    
    time_elapsed_seconds = (current_time - last_visit_time).total_seconds()
    
    # Regenerate taps
    regenerated_taps = int(time_elapsed_seconds * TAP_REGEN_RATE_PER_SECOND)
    game_data['taps_left'] = min(game_data['current_tap_limit'], game_data['taps_left'] + regenerated_taps)
    
    game_data['last_visit'] = current_time.isoformat() # Update last visit time
    return game_data

# --- Routes ---

@app.route('/')
def home_redirect():
    game_data = get_game_data(request)
    if not game_data.get('username'):
        return redirect(url_for('login'))
    return redirect(url_for('game'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        if not username:
            flash("Please enter a username!")
            return render_template('login.html')
        
        game_data = get_game_data(request)
        game_data['username'] = username # Set username
        
        # Initialize default game state for new users if it's their first time
        if game_data.get('score') is None:
            game_data['score'] = 0
            game_data['per_tap_bonus'] = 1
            game_data['current_tap_limit'] = DEFAULT_TAP_LIMIT
            game_data['taps_left'] = DEFAULT_TAP_LIMIT
            game_data['task_completed'] = False
            game_data['purchased_tap_upgrades'] = []
            game_data['purchased_limit_upgrades'] = []
            
        # Update last visit time upon login
        game_data['last_visit'] = datetime.now().isoformat()

        response = make_response(redirect(url_for('game')))
        return save_game_data(response, game_data)

    return render_template('login.html')

@app.route('/game')
def game():
    game_data = get_game_data(request)
    if not game_data.get('username'):
        return redirect(url_for('login'))

    # Calculate regenerated taps
    game_data = calculate_passive_income_and_regen_taps(game_data)

    # Check for daily bonus
    show_daily_bonus = False
    today_str = datetime.now().strftime('%Y-%m-%d')
    if game_data['claimed_daily_bonus_date'] != today_str:
        show_daily_bonus = True

    response = make_response(render_template('game.html',
                                             username=game_data['username'],
                                             score=game_data['score'],
                                             per_tap_bonus=game_data['per_tap_bonus'],
                                             taps_left=game_data['taps_left'],
                                             current_tap_limit=game_data['current_tap_limit'],
                                             show_daily_bonus=show_daily_bonus))
    return save_game_data(response, game_data)

@app.route('/click', methods=['POST'])
def click():
    game_data = get_game_data(request)
    if not game_data.get('username'):
        return redirect(url_for('login'))

    if game_data['taps_left'] > 0:
        game_data['score'] += game_data['per_tap_bonus']
        game_data['taps_left'] -= 1
        # Update last visit to correctly calculate regen after click
        game_data['last_visit'] = datetime.now().isoformat()
    else:
        flash("የመጫን ገደብህ አልቋል! ጠብቅ ወይም 'Tap Limit' Upgrade ግዛ።") # "Your tap limit is exhausted! Wait or buy 'Tap Limit' Upgrade."

    response = make_response(redirect(url_for('game')))
    return save_game_data(response, game_data)

@app.route('/claim_daily_bonus', methods=['POST'])
def claim_daily_bonus():
    game_data = get_game_data(request)
    if not game_data.get('username'):
        return redirect(url_for('login'))

    today_str = datetime.now().strftime('%Y-%m-%d')
    if game_data['claimed_daily_bonus_date'] != today_str:
        game_data['score'] += 1000
        game_data['claimed_daily_bonus_date'] = today_str
        flash("1000 ነጥብ ተቀብለሃል!")
    else:
        flash("የዛሬውን ቦነስ ከዚህ በፊት ተቀብለሃል!")

    response = make_response(redirect(url_for('game')))
    return save_game_data(response, game_data)

@app.route('/task')
def task_page():
    game_data = get_game_data(request)
    if not game_data.get('username'):
        return redirect(url_for('login'))
    
    return render_template('task.html', 
                           username=game_data['username'], 
                           score=game_data['score'],
                           task_completed=game_data['task_completed'])

@app.route('/complete_task', methods=['POST'])
def complete_task():
    game_data = get_game_data(request)
    if not game_data.get('username'):
        return redirect(url_for('login'))

    answer = request.form.get('answer', '').strip().lower()
    
    if answer == 'akalewold' and not game_data['task_completed']:
        game_data['score'] += 1000
        game_data['task_completed'] = True
        flash("ተግባር ተጠናቋል! 1000 ነጥብ አግኝተሃል!")
    elif game_data['task_completed']:
        flash("ይህን ተግባር ከዚህ በፊት አጠናቅቀሃል!")
    else:
        flash("ትክክለኛውን መልስ አላስገባህም!")
        
    response = make_response(redirect(url_for('task_page')))
    return save_game_data(response, game_data)

@app.route('/earn')
def earn_page():
    game_data = get_game_data(request)
    if not game_data.get('username'):
        return redirect(url_for('login'))
        
    return render_template('earn.html', 
                           score=game_data['score'], 
                           upgrades=TAP_UPGRADES,
                           purchased_upgrades=game_data['purchased_tap_upgrades'])

@app.route('/buy_tap_upgrade/<upgrade_id>', methods=['POST'])
def buy_tap_upgrade(upgrade_id):
    game_data = get_game_data(request)
    if not game_data.get('username'):
        return redirect(url_for('login'))

    upgrade = TAP_UPGRADES.get(upgrade_id)
    
    if upgrade and upgrade_id not in game_data['purchased_tap_upgrades']:
        if game_data['score'] >= upgrade['cost']:
            game_data['score'] -= upgrade['cost']
            game_data['per_tap_bonus'] += upgrade['per_tap_bonus']
            game_data['purchased_tap_upgrades'].append(upgrade_id)
            flash(f"{upgrade['name']} ገዝተሃል!")
        else:
            flash("በቂ ገንዘብ የለህም!")
    elif upgrade_id in game_data['purchased_tap_upgrades']:
        flash("ይህን upgrade ከዚህ በፊት ገዝተሃል!")
    
    response = make_response(redirect(url_for('earn_page')))
    return save_game_data(response, game_data)

@app.route('/members') # Based on user's last description for tap limit upgrades
def members_page():
    game_data = get_game_data(request)
    if not game_data.get('username'):
        return redirect(url_for('login'))
        
    return render_template('members.html', 
                           score=game_data['score'], 
                           upgrades=LIMIT_UPGRADES,
                           purchased_upgrades=game_data['purchased_limit_upgrades'])

@app.route('/buy_limit_upgrade/<upgrade_id>', methods=['POST'])
def buy_limit_upgrade(upgrade_id):
    game_data = get_game_data(request)
    if not game_data.get('username'):
        return redirect(url_for('login'))

    upgrade = LIMIT_UPGRADES.get(upgrade_id)
    
    if upgrade and upgrade_id not in game_data['purchased_limit_upgrades']:
        if game_data['score'] >= upgrade['cost']:
            game_data['score'] -= upgrade['cost']
            game_data['current_tap_limit'] += upgrade['bonus_limit']
            game_data['taps_left'] += upgrade['bonus_limit'] # Also add to current taps
            game_data['purchased_limit_upgrades'].append(upgrade_id)
            flash(f"{upgrade['name']} ገዝተሃል!")
        else:
            flash("በቂ ገንዘብ የለህም!")
    elif upgrade_id in game_data['purchased_limit_upgrades']:
        flash("ይህን upgrade ከዚህ በፊት ገዝተሃል!")
    
    response = make_response(redirect(url_for('members_page')))
    return save_game_data(response, game_data)

if __name__ == '__main__':
    app.run(debug=True)
