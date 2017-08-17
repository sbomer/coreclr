import sys
import os
import subprocess
import argparse

def executableName(name, platform):
    if platform == "Windows_NT":
        return name + ".exe"
    else:
        return name
    
def getRid(platform):
    if platform == "Linux":
        rid = "linux-x64"
    elif platform == "Windows_NT":
        rid = "win8-x64"
    elif platform == "OSX":
        rid = "osx.10.12-x64"
    else:
        assert(False)
    return rid

def isUnix(platform):
    if platform == "Windows_NT":
        return False
    return True

def clone_jitutils(destinationDir):
    jitutilsRepoName = "jitutils"
    jitutilsRepoPath = os.path.abspath(os.path.join(destinationDir, jitutilsRepoName))
    if os.path.isdir(jitutilsRepoPath):
        print(jitutilsRepoPath + " already exists. Assuming jitutils was already cloned.")
        return jitutilsRepoPath
    jitutilsRepoUrl = "https://github.com/dotnet/" + jitutilsRepoName + ".git"
    ret = subprocess.call(["git", "clone", jitutilsRepoUrl], cwd=destinationDir)
    if ret != 0:
        sys.exit("failed to clone " + jitutilsRepoUrl)
    return jitutilsRepoPath

def build_jitutils(dotnetPath, jitutilsPath, platform):
    jitutilsBinDir = os.path.abspath(os.path.join(jitutilsPath, "bin"))
    cijobs = os.path.join(jitutilsBinDir, executableName("cijobs", platform))
    jitdiff = os.path.join(jitutilsBinDir, executableName("jit-diff", platform))
    jitdasm = os.path.join(jitutilsBinDir, executableName("jit-dasm", platform))
    jitanalyze = os.path.join(jitutilsBinDir, executableName("jit-analyze", platform))

    if os.path.isfile(cijobs) and os.path.isfile(jitdiff) and os.path.isfile(jitdasm) and os.path.isfile(jitanalyze):
        print(jitutilsBinDir + " already contains cijobs, jit-diff, jit-dasm, and jit-analyze. Assuming jitutils was already built.")
        return (cijobs, jitdiff, jitdasm)

    rid = getRid(platform)
    ret = subprocess.call([dotnetPath, "restore", "-r", rid], cwd=jitutilsPath)
    if ret != 0:
        sys.exit("failed to restore " + jitutilsPath)
    ret = subprocess.call([dotnetPath, "publish", "-o", jitutilsBinDir, "-f", "netcoreapp2.0", "-r", rid], cwd=jitutilsPath)
    if ret != 0:
        sys.exit("failed to publish " + jitutilsPath)

    # workaround: copy wrapper scripts
    # ideally jitutils wouldn't use wrapper scripts, but jit-diff expects jit-dasm (no extension) to be on the path
    # instead of wrapper scripts, use the published/renamed host of the same name.
    # however, these aren't executable on linux, so we still need a workaround:
    # TODO: if os is linux:
    # TODO: remove this workaround once coreclr uses a recent enough cli (issue was fixed in https://github.com/dotnet/sdk/issues/1331)

#    if platform == "OSX":
#        shutil.copyfile(dotnetPath, os.path.join(jitutilsBinDir, "cijobs"))
#        shutil.copyfile(dotnetPath, os.path.join(jitutilsBinDir, "jit-diff"))
#        shutil.copyfile(dotnetPath, os.path.join(jitutilsBinDir, "jit-dasm"))
#        shutil.copyfile(dotnetPath, os.path.join(jitutilsBinDir, "jit-analyze"))
            
    if isUnix(platform):
        os.chmod(cijobs, 751)
        os.chmod(jitdiff, 751)
        os.chmod(jitdasm, 751)
        os.chmod(jitanalyze, 751)
        
    return (cijobs, jitdiff, jitdasm)

def locate_dotnet(coreclrDir, platform):

#    We may be able to use the Tools cli once DotnetCLIVersion.txt is updated.
#    The current version has a bug that prevents building jitutils.
    
    toolsPath = os.path.join(coreclrDir, "Tools")
    if not os.path.isdir(toolsPath):
        sys.exit("No Tools directory. Run init-tools first.")

    dotnetPath = os.path.join(toolsPath, "dotnetcli", executableName("dotnet", platform))

#    os = "Linux"
#    
#    if os == "Linux":
#        dotnetcliUrl = "https://download.microsoft.com/download/F/A/A/FAAE9280-F410-458E-8819-279C5A68EDCF/dotnet-sdk-2.0.0-preview2-006497-linux-x64.tar.gz"
#        dotnetcliFilename = os.path.join(coreclr, "dotnetcli-jitdiff.tar.gz")
# 
#    response = urllib2.urlopen(dotnetcliUrl)
#    request_url = response.geturl()
#    testfile = urllib.URLopener()
#    testfile.retrieve(request_url, dotnetcliFilename)
# 
#    if not os.path.isfile(dotnetcliFilename):
#        sys.exit("did not download .NET SDK")
# 
#    if platform == "Linux":
#        tar = tarfile.open(dotnetcliFilename)
#        tar.extractall(dotnetcliPath)
#        tar.close()
# 
#    if platform == "Linux":
#        dotnet = "dotnet"
# 
#    dotnetPath = os.path.join(dotnetcliPath
    if not os.path.isfile(dotnetPath):
        sys.exit("dotnet executable not found at " + dotnetPath)
 
    return dotnetPath

def main(argv):
    parser = argparse.ArgumentParser()
    required = parser.add_argument_group('required arguments')
    required.add_argument('-o', '--os', type=str, default=None, help='operating system')
    args, unknown = parser.parse_known_args(argv)
    if unknown:
        print('Ignoring argument(s): ', ','.join(unknown))

    if args.os is None:
        print('Specify --os')
        return -1

    # TODO: determine os if not passed
    platform = args.os

    # TODO: fix: script expects to be run from coreclr repo root
    coreclrDir = os.path.abspath(".")
    dotnetPath = locate_dotnet(coreclrDir, platform)
    toolsDir = os.path.join(coreclrDir, "Tools")
    if not os.path.isdir(toolsDir):
        sys.exit('Tools directory does not exist. Run init-tools first.')
        
    jitutilsRepoPath = clone_jitutils(toolsDir)
    (cijobs, jitdiff, jitdasm) = build_jitutils(dotnetPath, jitutilsRepoPath, platform)
    

if __name__ == '__main__':
    return_code = main(sys.argv[1:])
    sys.exit(return_code)
    
