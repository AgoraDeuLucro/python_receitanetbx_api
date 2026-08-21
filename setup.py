from setuptools import setup

with open("README.md", "r") as arq:
    readme = arq.read()

setup(name='py_receitanetbx',
    version='0.1.0',
    license='MIT License',
    author='Yuri Gomes',
    long_description=readme,
    long_description_content_type="text/markdown",
    author_email='yurialdegomes@gmail.com',
    keywords='receitanetbx receita federal sped efd ecf soap',
    description=u'Wrapper não oficial do ReceitanetBX (Receita Federal)',
    packages=['py_receitanetbx'],
    install_requires=['requests'],)
