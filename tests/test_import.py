
def test_import_all():

    # ignore the deprecation warnings of yaql and aoihttp
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    import slacktivate
    import slacktivate.cli.helpers
    import slacktivate.cli.logo
    import slacktivate.cli
    import slacktivate.helpers.collections
    import slacktivate.helpers.dict_serializer
    import slacktivate.helpers.photo
    import slacktivate.helpers
    import slacktivate.input.config
    import slacktivate.input.helpers
    import slacktivate.input.parsing
    import slacktivate.input
    import slacktivate.macros.provision
    import slacktivate.macros.manage
    import slacktivate.macros
    import slacktivate.slack.classes
    import slacktivate.slack.clients
    import slacktivate.slack.exceptions
    import slacktivate.slack.methods
    import slacktivate.slack.retry
    import slacktivate.slack

    assert True

