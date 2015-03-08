import fnmatch
import hashlib
import os
import shutil
import stat
import subprocess
import tarfile
import urllib
import zipfile
from waflib import Logs
from waflib.extras.preparation import PreparationContext
from waflib.extras.build_status import BuildStatus

__downloadUrl = 'https://googletest.googlecode.com/files/%s'
__srcFile = 'gmock-1.7.0.zip'
__srcSha256Checksum = '\x26\xfc\xbb\x59\x25\xb7\x4a\xd5\xfc\x8c\x26\xb0\x49\x5d\xfc\x96\x35\x3f\x4d\x55\x34\x92\xeb\x97\xe8\x5a\x8a\x6d\x2f\x43\x09\x5b'
__srcDir = 'src'

def options(optCtx):
    optCtx.load('compiler_cxx dep_resolver')

def prepare(prepCtx):
    prepCtx.options.dep_base_dir = prepCtx.srcnode.find_dir('..').abspath()
    prepCtx.load('dep_resolver')
    status = BuildStatus.init(prepCtx.path.abspath())
    if status.isSuccess():
	prepCtx.msg('Preparation already complete', 'skipping')
	return
    filePath = os.path.join(prepCtx.path.abspath(), __srcFile)
    url = __downloadUrl % __srcFile
    if os.access(filePath, os.R_OK):
	hasher = hashlib.sha256()
	handle = open(filePath, 'rb')
	try:
	    hasher.update(handle.read())
	finally:
	    handle.close()
	if hasher.digest() != __srcSha256Checksum:
	    os.remove(filePath)
    if os.access(filePath, os.R_OK):
	prepCtx.start_msg('Using existing source file')
	prepCtx.end_msg(filePath)
    else:
	prepCtx.start_msg('Downloading %s' % url)
	triesRemaining = 10
	while triesRemaining > 1:
	    try:
		urllib.urlretrieve(url, filePath)
		break
	    except urllib.ContentTooShortError:
		triesRemaining -= 1
		if os.path.exists(filePath):
		    os.remove(filePath)
	else:
	    prepCtx.fatal('Could not download %s' % url)
	prepCtx.end_msg('Saved to %s' % filePath)
    srcPath = os.path.join(prepCtx.path.abspath(), __srcDir)
    extractPath = os.path.join(prepCtx.path.abspath(), 'gmock-1.7.0')
    binPath = os.path.join(prepCtx.path.abspath(), 'bin')
    libPath = os.path.join(prepCtx.path.abspath(), 'lib')
    includePath = os.path.join(prepCtx.path.abspath(), 'include')
    for path in [srcPath, extractPath, binPath, libPath, includePath]:
	if os.path.exists(path):
	    if os.path.isdir(path):
		shutil.rmtree(path)
	    else:
		os.remove(path)
    prepCtx.start_msg('Extracting files to')
    handle = zipfile.ZipFile(filePath, 'r')
    handle.extractall(prepCtx.path.abspath())
    os.rename(extractPath, srcPath)
    prepCtx.end_msg(srcPath)
    for dirPath, subDirList, fileList in os.walk(os.path.join(srcPath, 'scripts')):
	for file in fileList:
	    os.chmod(os.path.join(dirPath, file), stat.S_IXUSR | stat.S_IRUSR | stat.S_IWUSR)
    for dirPath, subDirList, fileList in os.walk(os.path.join(srcPath, 'gtest', 'scripts')):
	for file in fileList:
	    os.chmod(os.path.join(dirPath, file), stat.S_IXUSR | stat.S_IRUSR | stat.S_IWUSR)

def configure(confCtx):
    confCtx.load('compiler_cxx dep_resolver')
    status = BuildStatus.init(confCtx.path.abspath())
    if status.isSuccess():
	confCtx.msg('Configuration already complete', 'skipping')
	return
    srcPath = os.path.join(confCtx.path.abspath(), __srcDir)
    os.chdir(srcPath)
    if confCtx.options.gtest_binpath is not None and confCtx.options.gtest_binpath != '':
	gtestArg = '--with-gtest=%s' % os.path.dirname(confCtx.options.gtest_binpath)
    else:
	gtestArg = ''
    if os.name == 'posix':
	returnCode = subprocess.call([
		'sh',
		os.path.join(srcPath, 'configure'),
		'--prefix=%s' % confCtx.srcnode.abspath(),
		gtestArg])
	if returnCode != 0:
	    confCtx.fatal('Google Mock configure failed: %d' % returnCode)
    elif os.name == 'nt':
	# Nothing to do, just use the provided VS solution
	return
    else:
	confCtx.fatal('Unsupported OS %s' % os.name)

def build(buildCtx):
    status = BuildStatus.load(buildCtx.path.abspath())
    if status.isSuccess():
	Logs.pprint('NORMAL', 'Build already complete                   :', sep='')
	Logs.pprint('GREEN', 'skipping')
	return
    srcPath = os.path.join(buildCtx.path.abspath(), __srcDir)
    os.chdir(srcPath)
    if os.name == 'posix':
	returnCode = subprocess.call([
		'make'])
    elif os.name == 'nt':
	returnCode = subprocess.call([
		'devenv.com',
		os.path.join(srcPath, 'msvc', '2010', 'gmock.sln')])
    else:
	confCtx.fatal('Unsupported OS %s' % os.name)
    if returnCode != 0:
	buildCtx.fatal('Google Mock build failed: %d' % returnCode)
    libPath = os.path.join(buildCtx.path.abspath(), 'lib')
    os.mkdir(libPath)
    for dirPath, subDirList, fileList in os.walk(os.path.join(srcPath, 'lib')):
	for file in fileList:
	    if fnmatch.fnmatch(file, 'libgmock*'):
		filePath = os.path.join(dirPath, file)
		if os.path.islink(filePath):
		    linkTgt = os.readlink(filePath)
		    linkSrc = os.path.join(libPath, file)
		    if not os.path.exists(linkSrc):
			os.symlink(linkTgt, os.path.join(libPath, file))
		else:
		    shutil.copy2(os.path.join(dirPath, file), libPath)
    shutil.copytree(os.path.join(srcPath, 'include'), os.path.join(buildCtx.path.abspath(), 'include'))
    status.setSuccess()
