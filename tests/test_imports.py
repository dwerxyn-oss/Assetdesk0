def test_application_imports() -> None:
    import app.handlers.admin.broadcast
    import app.handlers.admin.rewards
    import app.handlers.admin.sells
    import app.handlers.admin.tasks_admin
    import app.handlers.admin.users
    import app.handlers.admin.withdrawals
    import app.main
    from app.db.session import create_engine, create_session_factory
    from app.main import build_dispatcher

    dispatcher = build_dispatcher(create_session_factory(create_engine()))
    names = [router.name for router in dispatcher.sub_routers]
    assert names[0] == "admin"
    assert "public" in names
    assert app.main.main
    assert app.handlers.admin.users.router
