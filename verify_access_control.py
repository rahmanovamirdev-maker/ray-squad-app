from app import (
    app,
    db,
    User,
    TeamCore,
    TeamSubCore,
    is_global_team_manager,
    get_user_managed_teams,
    can_access_team_panel,
    can_administer_team,
    can_manage_core,
    can_manage_subcore,
)


def get_or_create_user(username, team=None, is_admin=False, is_owner=False, prefix=None):
    u = User.query.filter_by(username=username).first()
    if not u:
        from werkzeug.security import generate_password_hash
        u = User(
            username=username,
            password_hash=generate_password_hash('tmp-pass-123'),
            team=team,
            is_admin=is_admin,
            is_owner=is_owner,
            prefix=prefix,
        )
        db.session.add(u)
        db.session.flush()
    return u


with app.app_context():
    # Берем реальную структуру команды для проверки
    core = TeamCore.query.filter_by(team_name='Delta', core_index=1).first()
    assert core is not None, 'Не найдена TeamCore Delta/1'
    subcore = TeamSubCore.query.filter_by(core_id=core.id, subcore_index=1).first()
    assert subcore is not None, 'Не найдена TeamSubCore Delta/1.1'

    owner = get_or_create_user('verify_owner', is_admin=True, is_owner=True, prefix='Developer')
    team_admin = get_or_create_user('verify_team_admin', team='Delta', is_admin=True, prefix=None)
    moderator = get_or_create_user('verify_moderator', team='Delta', is_admin=False, prefix='Moderator')
    outsider = get_or_create_user('verify_outsider', team='Rey', is_admin=False, prefix=None)

    core_lead = get_or_create_user('verify_core_lead', team='Delta', is_admin=False, prefix=None)
    subcore_lead = get_or_create_user('verify_subcore_lead', team='Delta', is_admin=False, prefix=None)

    core.lead_user_id = core_lead.id
    subcore.lead_user_id = subcore_lead.id
    db.session.commit()

    results = []

    results.append(('owner_global', is_global_team_manager(owner)))
    results.append(('team_admin_global', is_global_team_manager(team_admin)))
    results.append(('moderator_global', is_global_team_manager(moderator)))

    managed_owner = sorted(get_user_managed_teams(owner))
    managed_admin = sorted(get_user_managed_teams(team_admin))
    managed_mod = sorted(get_user_managed_teams(moderator))
    managed_core_lead = sorted(get_user_managed_teams(core_lead))
    managed_subcore_lead = sorted(get_user_managed_teams(subcore_lead))

    results.append(('owner_can_access_panel', can_access_team_panel(owner)))
    results.append(('team_admin_can_access_panel', can_access_team_panel(team_admin)))
    results.append(('moderator_can_access_panel', can_access_team_panel(moderator)))
    results.append(('outsider_can_access_panel', can_access_team_panel(outsider)))

    results.append(('admin_can_administer_delta', can_administer_team(team_admin, 'Delta')))
    results.append(('admin_can_administer_rey', can_administer_team(team_admin, 'Rey')))
    results.append(('moderator_can_administer_delta', can_administer_team(moderator, 'Delta')))

    results.append(('core_lead_manage_core', can_manage_core(core_lead, core)))
    results.append(('subcore_lead_manage_core', can_manage_core(subcore_lead, core)))
    results.append(('core_lead_manage_subcore', can_manage_subcore(core_lead, subcore)))
    results.append(('subcore_lead_manage_subcore', can_manage_subcore(subcore_lead, subcore)))
    results.append(('outsider_manage_subcore', can_manage_subcore(outsider, subcore)))

    print('MANAGED_TEAMS owner=', managed_owner)
    print('MANAGED_TEAMS team_admin=', managed_admin)
    print('MANAGED_TEAMS moderator=', managed_mod)
    print('MANAGED_TEAMS core_lead=', managed_core_lead)
    print('MANAGED_TEAMS subcore_lead=', managed_subcore_lead)

    for name, value in results:
        print(f'{name}={value}')
