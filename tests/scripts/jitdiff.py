#!/usr/bin/env python
#
## Licensed to the .NET Foundation under one or more agreements.
## The .NET Foundation licenses this file to you under the MIT license.
## See the LICENSE file in the project root for more information.
#
##
# Title               :jitdiff.py
#
import sys
import os
import subprocess

def executableName(name, platform):
    if platform == "Windows_NT":
        return name + ".exe"
    else:
        return name

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
    if platform == "Linux":
        rid = "linux-x64"
    elif platform == "Windows_NT":
        rid = "win8-x64"
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
    if platform == "Linux" or platform == "OSX":
        os.chmod(cijobs, 751)
        os.chmod(jitdiff, 751)
        os.chmod(jitdasm, 751)
        os.chmod(jitanalyze, 751)
        
    return (cijobs, jitdiff, jitdasm)

def obtain_product_build(cijobs, commit, localJobDir, jenkinsJobName, platform, arch, config):
    outputDir = os.path.join(localJobDir, commit, "bin")
    outputBinDir = os.path.join(outputDir, "Product", platform + "." + arch + "." + config)
    if os.path.isdir(outputBinDir):
        print(outputBinDir + " already exists. Assuming artifacts for commit " + commit + " were already downloaded")
        return outputBinDir
    
    # print(dotnetPath + " " + cijobs + " copy --job " + jobName + " --commit " + commit + " --output " + outputDir)
    # todo: if this commit doesn't have a job? or if it's unsuccessful?
    ret = subprocess.call([cijobs, "copy",
                           "--job", jenkinsJobName,
                           "--commit", commit,
                           "--output", outputDir,
                           "--unzip"])
    if ret != 0 or not os.path.isdir(outputBinDir):
        sys.exit("failed to obtain product build for commit " + commit + ", job " + jenkinsJobName)
    return outputBinDir

def obtain_windows_test_build(cijobs, coreclrDir, win_arch, win_config):
    # TODO: remove this entire function once we don't depend on
    # windows to build tests. Ideally we would obtain tests from a
    # linux job.
    #dotnet_coreclr/master/config_windows_nt_bld
    #CORECLR_WINDOWS_BUILD
    # TODO: parameterize by arch, config
    windowsTestBinDir = os.path.join(coreclrDir, "bin", "tests", "Windows_NT." + win_arch + "." + win_config)
    if os.path.isdir(windowsTestBinDir):
        print(windowsTestBinDir + " already exists. Assuming artifacts for windows test build were already downloaded")
        return windowsTestBinDir
    jenkinsJobName = "checked_windows_nt_bld"
    # TODO: which commit to download?
    ret = subprocess.call([cijobs, "copy",
                           "--job", jenkinsJobName,
                           "--output", windowsTestBinDir,
                           "--last_successful",
                           "--ContentPath", "artifact/bin/tests/tests.zip"])
    # We can't pass the --unzip argument here, because the zip file
    # contains backslash separators and cijobs will (correctly)
    # interpret these as part of the filename on non-windows
    # platforms. This happens because the zip file is created in
    # netci.groovy using an old version of the framework that treats
    # path separators incorrectly. Once the netci.groovy jobs run on
    # machines with .NET 4.6.1 or later, this should be fixed:
    # https://docs.microsoft.com/en-us/dotnet/framework/migration-guide/mitigation-ziparchiveentry-fullname-path-separator
    if ret != 0 or not os.path.isdir(windowsTestBinDir):
        sys.exit("failed to obtain windows test build")
    ret = subprocess.call(["unzip", "-q", os.path.join(windowsTestBinDir, "tests.zip"), "-d", windowsTestBinDir])
    if ret > 1:
        sys.exit("failed to unzip windows test build")
    return windowsTestBinDir


def obtain_unix_test_build(cijobs, coreclrDir, commit, localJobDir, jenkinsJobName, platform, arch, config):
    outputDir = os.path.join(localJobDir, commit, "bin")
    unixTestBinDir = os.path.join(outputDir, "obj", platform + "." + arch + "." + config, "tests")
    if os.path.isdir(unixTestBinDir):
        print(unixTestBinDir + " already exists. Assuming artifacts for unix test build were already downloaded")
        return unixTestBinDir
    ret = subprocess.call([cijobs, "copy",
                           "--job", jenkinsJobName,
                           "--output", outputDir,
                           "--last_successful",
                           "--ContentPath", "artifact/bin/obj/*zip*/obj.zip",
                           "--unzip"])
    if ret != 0 or not os.path.isdir(unixTestBinDir):
        sys.exit("failed to obtain test build for commit " + commit)
    return unixTestBinDir

def obtain_corefx_build(cijobs, coreclrDir, jenkinsJobName):
    #for ubuntu, osjobname is 'ubuntu14.04'.
    #for other os's, osjobname is os.tolowercase
    #dotnet_corefx/master/osjobname_release94
    #use last successful build
    outputDir = os.path.join(coreclrDir, "bin", "CoreFxBinDir")
    if os.path.isdir(outputDir):
        print(outputDir + " already exists. Assuming artifacts for corefx build were already downloaded")
        return outputDir
    # TODO: which commit?
    ret = subprocess.call([cijobs, "copy",
                           "--repo", "dotnet_corefx",
                           "--job", jenkinsJobName,
                           "--output", outputDir,
                           "--last_successful",
                           "--ContentPath", "artifact/bin/build.tar.gz"])
    if ret != 0 or not os.path.isdir(outputDir):
        sys.exit("failed to obtain corefx build")
        
    ret = subprocess.call(["tar", "-xf", os.path.join(outputDir, "build.tar.gz"), "-C", outputDir])
    if ret != 0:
        sys.exit("failed to extract corefx build")
    return outputDir

#def getFullJobName(jobName, isPR, folder):
#    jobSuffix = ""
#    if isPR:
#        jobSuffix = "_prtest"
#    folderPrefix = ""
#    if folder != "":
#        folderPrefix = folder + "/"
#    fullJobName = folderPrefix + jobName + jobSuffix



def generate_coreroot(coreclrDir, currentBinDir, windowsTestBinDir, unixTestBinDir, corefxBinDir):
    # coreroot is the directory that contains tests, test dependencies, the framework, and our built product.
    # it looks like on windows, the framework dependencies get restored as packages.
    # we can build tests on unix (maybe with some caveats), but it's apparantly slow
    # running tests: instructions and ci still have to copy over windows test build, and generate an overlay from the win build, linux build, and linux corefx build

    # for now: try building test overlay on linux only:
    # (prob. still have to do the runtest --corefxbindir, etc.)

    # ideally, would have this pull down coreroot from ci servers
    # conflict: building locally, vs using ci artifacts?
    # be flexible: use either.
    # prefer local build if available > retrieve from ci > initiate build locally
    
    # TODO: fix this to work on windows too

    # OH: looks like we DO archive test build on linux and osx.
    #                       // Basic archiving of the build
    #                   Utilities.addArchival(newJob, "bin/Product/**,bin/obj/*/tests/**/*.dylib,bin/obj/*/tests/**/*.so", "bin/Product/**/.nuget/**")
    #                   // And pal tests
    #                   Utilities.addXUnitDotNETResults(newJob, '**/pal_tests.xml')


    # inputs: win test build, native test build, prod build, corefx bin.
    # need sources to be available in order to call runtest.sh
    overlayDir = os.path.join(windowsTestBinDir, "Tests", "coreoverlay")
    if os.path.isdir(overlayDir):
        print(overlayDir + " already exists. Assuming coreoverlay has already been generated")
        return overlayDir
    ret = subprocess.call([os.path.join(coreclrDir, "tests", "runtest.sh"),
                           "--testRootDir=" + windowsTestBinDir,
                           "--testNativeBinDir=" + unixTestBinDir,
                           "--coreClrBinDir=" + currentBinDir,
                           "--mscorlibDir=" + currentBinDir,
                           "--coreFxBinDir=" + corefxBinDir,
                           "--build-overlay-only"])
    if ret != 0:
        sys.exit("failed to build overlay")
    return overlayDir
    

def runJitdiff(jitdiff, jitdasm, currentBinDir, baseBinDir, overlayDir, windowsTestBinDir, jitdiffDir):
    crossgenName = "crossgen"
    crossgen = os.path.join(currentBinDir, crossgenName)
    if not os.path.isfile(crossgen):
        sys.exit("crossgen executable does not exist in " + crossgen)

    if platform == "Linux" or platform == "OSX":
        os.chmod(crossgen, 751)
    # jit-diff takas as input: directories containing the base and diff jits, a core_root containing the platform assemblies, and a crossgen exe.


    diffDir = os.path.join(jitdiffDir, "diffs")
    if not os.path.isdir(diffDir):
        os.makedirs(diffDir)

    # problem: we crossgen SPC by default now, so jitdiff fails when using the 'crossgen' default
    # don't crossgen SPC by default with jit-diff.
    print(jitdiff + " diff --base " + baseBinDir + " --diff " + currentBinDir + " --crossgen " + crossgen + " --core_root")
    jitdiff_env = os.environ
    jitdiff_env["PATH"] = os.path.dirname(jitdasm) + os.pathsep + jitdiff_env["PATH"]
    ret = subprocess.call([jitdiff, "diff",
                           "--base", baseBinDir,
                           "--diff", currentBinDir,
                           "--crossgen", crossgen,
                           "--core_root", overlayDir,
                           "--test_root", windowsTestBinDir,
                           "--output", diffDir,
                           "--corelib"],
#                           "--frameworks",
#                           "--tests"],
                          env=jitdiff_env)
    return ret


def getJenkinsJobName(platform, arch, config, isPr = False):
    if platform == "Linux":
        jobPlatform = "ubuntu"
    elif platform == "Windows_NT":
        jobPlatform = "windows_nt"
    assert(arch == "x64")
    assert(config == "Checked")
    jobName = config.lower() + "_" + jobPlatform
    if isPr:
        jobName += "_prtest"
    return jobName

def main(argv):
    # TODO: fix: script expects to be run from coreclr repo root
    coreclrDir = os.path.abspath(".")

    # platform = "Linux"
    platform = "Windows_NT"
    arch = "x64"
    config = "Checked"
    jenkinsJobName = getJenkinsJobName(platform, arch, config)
    jenkinsJobNamePR = getJenkinsJobName(platform, arch, config, isPr = True)
    
    jitdiffDir = os.path.join(coreclrDir, "jitdiff")
    if not os.path.isdir(jitdiffDir):
        os.makedirs(jitdiffDir)
    
    dotnetPath = locate_dotnet(coreclrDir, platform)
    jitutilsRepoPath = clone_jitutils(jitdiffDir)
    (cijobs, jitdiff, jitdasm) = build_jitutils(dotnetPath, jitutilsRepoPath, platform)


    # for PR commits, the jenkins job is run on a merge commit.
    # the first parent (^1) is the base commit
    # the second parent (^2) is the PR commit
    # we want diff between the base commit and the merge commit

    # for non-pr jobs? diff between HEAD and previous commit.
    # problem: the job merge commit seems to be a merge commit of the PR commit into the current master.
    # however, when more commits are made to the master branch, the github merge commit is also updated.
    # thus PR merge commits quickly go out of date when the repo is updated with new commits.
    # this just means it's hard to check out a github merge commit locally and run jit-diff.
    # should be fine in ci though.
    # it should be possible to check out a github PR commit, and diff it with the current master (the would-be merge base?)
    # let's try that instead for now, but the PR jobs should definitely use the base commit of the merge.
    
    current_commit = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode('utf-8').strip()
    print("current commit: " + current_commit)
    base_commit = subprocess.check_output(["git", "rev-parse", "master"]).decode('utf-8').strip()
    print("base commit: " + base_commit)
    # test joe's pr: https://ci.dot.net/job/dotnet_coreclr/job/master/job/checked_ubuntu_prtest/9654/
    current_commit = "06b01cb956955f7c85683a973abf24f9e0985418"
    # https://ci.dot.net/job/dotnet_coreclr/job/master/job/checked_ubuntu/9603/
    base_commit = "95b075fbdaee0c98b1527530787df708607063ae"

    localJobDir = os.path.join(jitdiffDir, "artifacts")
    if not os.path.isdir(localJobDir):
        os.makedirs(localJobDir)
    
    currentBinDir = obtain_product_build(cijobs, current_commit, localJobDir, jenkinsJobNamePR, platform, arch, config)
    baseBinDir = obtain_product_build(cijobs, base_commit, localJobDir, jenkinsJobName, platform, arch, config)

    currentCoreclrDir = os.path.join(localJobDir, current_commit)
    
    windowsTestBinDir = obtain_windows_test_build(cijobs, currentCoreclrDir, arch, config)
    unixTestBinDir = obtain_unix_test_build(cijobs, currentCoreclrDir, current_commit, localJobDir, jenkinsJobNamePR, platform, arch, config)
    corefxBinDir = obtain_corefx_build(cijobs, currentCoreclrDir, jenkinsJobName = "ubuntu14.04_release")
    overlayDir = generate_coreroot(coreclrDir, currentBinDir, windowsTestBinDir, unixTestBinDir, corefxBinDir)

    ret = runJitdiff(jitdiff, jitdasm, currentBinDir, baseBinDir, overlayDir, windowsTestBinDir, jitdiffDir)
    

    # we need core_root to contain the dependencies of the stuff we're crossgen'ing.
    # usually this will be available whenever we have managed dlls as inputs anyway.
    # question is: what inputs do we use? everything!
    # (tests, and frameworks)
    # this means we need the built test dlls and framework dlls to be available
    # they come from a flow job in ci.

    # do the same thing as the netci.groovy jobs, except using cijobs,
    # to make it locally reproducible.

    # need to generate a core_root.
    # usually this is done by downloading some builds, and running runtest.sh

    # apparently linux test build isn't quite at parity with windows test build, and it's slow. :(
    # for now we need to generate a core_root by calling runtests.sh

    if ret != 0:
        print("jit-diff returned with " + str(ret) + " errors")
    
    
if __name__ == '__main__':
    return_code = main(sys.argv[1:])
    sys.exit(return_code)
