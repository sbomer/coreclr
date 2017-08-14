def clone_jitutils(jitdiffDir):
    jitutilsRepoName = "jitutils"
    jitutilsRepoPath = os.path.abspath(os.path.join(jitdiffDir, jitutilsRepoName))
    if os.path.isdir(jitutilsRepoPath):
        print(jitutilsRepoPath + " already exists. Assuming jitutils was already cloned.")
        return jitutilsRepoPath
    jitutilsRepoUrl = "https://github.com/dotnet/" + jitutilsRepoName + ".git"
    ret = subprocess.call(["git", "clone", jitutilsRepoUrl], cwd=jitdiffDir)
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
