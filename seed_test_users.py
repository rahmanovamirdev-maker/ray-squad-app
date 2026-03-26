from werkzeug.security import generate_password_hash

from app import (
    app,
    db,
    User,
    TeamCore,
    TeamSubCore,
    TeamAcademSlot,
    ensure_team_structure_seed,
    VALID_TEAMS,
)

TEAM_SLUGS = {
    'Delta': 'delta',
    'Den': 'den',
    'ХАЦКЕР': 'hacker',
    '404': 't404',
    'Bobik': 'bobik',
    'Oir': 'oir',
    'Gordon': 'gordon',
    'Rey': 'rey',
}

DEFAULT_PASSWORD = 'Test123!Pass'


def seed_test_users():
    created = 0
    assigned = 0

    ensure_team_structure_seed()

    for team in VALID_TEAMS:
        slug = TEAM_SLUGS.get(team, team.lower())
        users_for_team = []

        for i in range(1, 13):
            username = f'test_{slug}_{i:02d}'
            user = User.query.filter_by(username=username).first()
            if not user:
                user = User(
                    username=username,
                    password_hash=generate_password_hash(DEFAULT_PASSWORD),
                    display_name=f'Test {team} #{i:02d}',
                    team=team,
                    is_admin=(i == 1),
                    prefix='Moderator' if i == 1 else None,
                )
                db.session.add(user)
                created += 1
            else:
                if user.team != team:
                    user.team = team
            users_for_team.append(user)

        db.session.flush()

        slots = (
            TeamAcademSlot.query
            .join(TeamSubCore, TeamSubCore.id == TeamAcademSlot.subcore_id)
            .join(TeamCore, TeamCore.id == TeamSubCore.core_id)
            .filter(TeamCore.team_name == team)
            .order_by(TeamCore.core_index.asc(), TeamSubCore.subcore_index.asc(), TeamAcademSlot.slot_index.asc())
            .all()
        )

        for user in users_for_team[:8]:
            if TeamAcademSlot.query.filter_by(user_id=user.id).first():
                continue
            free_slot = next((s for s in slots if s.user_id is None), None)
            if not free_slot:
                break
            free_slot.user_id = user.id
            assigned += 1

    db.session.commit()
    print(f'CREATED_USERS={created}')
    print(f'ASSIGNED_SLOTS={assigned}')
    print(f'DEFAULT_PASSWORD={DEFAULT_PASSWORD}')


if __name__ == '__main__':
    with app.app_context():
        seed_test_users()
