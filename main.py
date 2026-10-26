from dify_plugin import Plugin

from runtime_config import get_plugin_env


plugin = Plugin(get_plugin_env())


if __name__ == "__main__":
    plugin.run()

