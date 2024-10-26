from setuptools import setup, find_packages

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

with open('requirements-dev.txt') as f:
    requirements_dev = f.read().splitlines()

setup(
    name='kb-chatbot',
    version='0.2.0',
    author='Nestor Urquiza',
    author_email='nestor.urquiza@gmail.com',
    description='A chatbot that syncs various sources to a vector DB and uses RAG to interact with ChatGPT.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/nestoru/kb-chatbot',
    packages=find_packages(),
    install_requires=requirements,
    extras_require={
        'dev': requirements_dev,
    },
    entry_points={
        'console_scripts': [
            "kb-onenote-sync=kb_chatbot.sync.onenote:main",
            "kb-sync-onedrive=kb_chatbot.sync.onedrive:main",
            "kb-inference=kb_chatbot.inference:main",
            "kb-rag=kb_chatbot.rag:main",
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.7',
)
