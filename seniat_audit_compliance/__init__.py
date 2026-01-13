from . import models
from . import controllers
from .hooks import post_init_setup_seniat_user

def post_init_hook(env):
    post_init_setup_seniat_user(env)