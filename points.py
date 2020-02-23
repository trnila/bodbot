import csv
import logging
from collections import OrderedDict, namedtuple
import aiohttp

logger = logging.getLogger(__name__)

def extract_tasks(row):
    results = OrderedDict()
    for task, score in row.items():
        if score and task and task not in ['name', 'login']:
            results[task] = int(score)
    return results

def parse(text):
    reader = csv.DictReader(text.splitlines())
    students = {}
    mins = {}
    maxs = {}
   
    for row in reader:
        login = row['login']
        if not login:
            continue

        if login == 'min':
            mins = extract_tasks(row)
            continue
        if login == 'max':
            maxs = extract_tasks(row)
            continue

        login = login.upper()
        students[login] = extract_tasks(row)

    return (mins, maxs, students)

parse(open("a.csv").read())

Task = namedtuple('Task', ['name', 'points', 'min', 'max'])

class Class:
    def __init__(self, name, url):
        self.name = name
        self.url = url
        self.students = {}
        self.mins = {}
        self.maxs = {}

    async def sync(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(self.url) as response:
                text = await response.text()
                self.mins, self.maxs, self.students = parse(text)

        from pprint import pprint
        pprint(self.students)

    async def for_student(self, login):
        login = login.upper()
        if login not in self.students:
            return None
        
        result = []
        for task, pts in self.students[login].items():
            t = Task(
                name=task,
                points=pts,
                min=self.mins.get(task),
                max=self.maxs.get(task)
            )
            result.append(t)
        return result


class Points:
    def __init__(self):
        self.classes = []

    def add_class(self, name, url):
        logger.debug("adding class %s", name)
        self.classes.append(Class(name, url))

    async def sync(self):
        for clazz in self.classes:
            await clazz.sync()

    async def for_student(self, login):
        for clazz in self.classes:
            result = await clazz.for_student(login)
            if result:
                return result
