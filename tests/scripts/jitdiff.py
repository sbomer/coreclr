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
import argparse

from build_jitutils import *


def obtain_product_build(cijobs, commit, localJobDir, jenkinsJobName, platform, arch, config):
    outputDir = os.path.join(localJobDir, commit, "bin")
    outputBinDir = os.path.join(outputDir, "Product", platform + "." + arch + "." + config)
    if os.path.isdir(outputBinDir):
        # print(outputBinDir + " already exists.")
        print("Assuming artifacts for commit " + commit + " were already downloaded")
        return outputBinDir
    
    print(cijobs + " copy --job " + jenkinsJobName + " --commit " + commit + " --output " + outputDir)
    # todo: if this commit doesn't have a job? or if it's unsuccessful?
    ret = subprocess.call([cijobs, "copy",
                           "--job", jenkinsJobName,
                           "--commit", commit,
                           "--output", outputDir,
                           "--unzip"])
    if ret != 0 or not os.path.isdir(outputBinDir):
        sys.exit("failed to obtain product build for commit " + commit + ", job " + jenkinsJobName)
    return outputBinDir

def obtain_windows_test_build(cijobs, coreclrDir, commit, platform, win_arch, win_config):
    # TODO: make this work for any platform's test build, once we don't depend on
    # windows to build tests. Ideally we would obtain tests from a
    # linux job for linux, etc.
    #dotnet_coreclr/master/config_windows_nt_bld
    #CORECLR_WINDOWS_BUILD
    # TODO: parameterize by arch, config
    windowsTestBinDir = os.path.join(coreclrDir, "bin", "tests", "Windows_NT." + win_arch + "." + win_config)
    if os.path.isdir(windowsTestBinDir):
        print(windowsTestBinDir + " already exists. Assuming artifacts for windows test build were already downloaded")
        return windowsTestBinDir
    jenkinsJobName = "checked_windows_nt_bld"
    # TODO: which commit to download?
    command = [cijobs, "copy",
               "--job", jenkinsJobName,
               "--output", windowsTestBinDir,
               "--commit", commit,
               "--ContentPath", "artifact/bin/tests/tests.zip"]
    if platform == "Windows_NT":
        command.append("--unzip")
    ret = subprocess.call(command)
    if ret != 0 or not os.path.isdir(windowsTestBinDir):
            sys.exit("failed to obtain windows test build") 

    if platform == "Windows_NT":
        return windowsTestBinDir
    else:
        # We can't pass the --unzip argument here, because the zip file
        # contains backslash separators and cijobs will (correctly)
        # interpret these as part of the filename on non-windows
        # platforms. This happens because the zip file is created in
        # netci.groovy using an old version of the framework that treats
        # path separators incorrectly. Once the netci.groovy jobs run on
        # machines with .NET 4.6.1 or later, this should be fixed:
        # https://docs.microsoft.com/en-us/dotnet/framework/migration-guide/mitigation-ziparchiveentry-fullname-path-separator
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


def generate_overlay(coreclrDir, currentBinDir, windowsTestBinDir, unixTestBinDir, corefxBinDir):
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
    

def runJitdiff(jitdiff, jitdasm, currentBinDir, baseBinDir, coreRoot, testBinDir, jitdiffDir, platform):
    crossgen = os.path.join(currentBinDir, executableName("crossgen", platform))
    if not os.path.isfile(crossgen):
        sys.exit("crossgen executable does not exist in " + crossgen)

    if isUnix(platform):
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
                           "--core_root", coreRoot,
                           "--test_root", testBinDir,
                           "--output", diffDir,
#                           "--corelib"],
                           "--frameworks"],
#                           "--tests"],
                          env=jitdiff_env)
    return ret


def getJenkinsJobName(platform, arch, config, isPr = False):
    if platform == "Linux":
        jobPlatform = "ubuntu"
    elif platform == "Windows_NT":
        jobPlatform = "windows_nt"
    elif platform == "OSX":
        jobPlatform = "osx10.12"
    else:
        assert(False)

    assert(arch == "x64")
    assert(config == "Checked")

    jobName = config.lower() + "_" + jobPlatform
    if isPr:
        jobName += "_prtest"
    return jobName

def main(argv):
    parser = argparse.ArgumentParser()
    required = parser.add_argument_group('required arguments')
    required.add_argument('-o', '--os', type=str, default=None, help='operating system')
    required.add_argument('-r', '--revision', type=str, default=None, help='revision')
    args, unknown = parser.parse_known_args(argv)

    if unknown:
        print('Ignoring argument(s): ', ','.join(unknown))

    if args.os is None:
        print('Specify --os')
        return -1

    if args.revision is None:
        print('specify --revision')
        return -1

    # TODO: determine os if not passed
    platform = args.os
    # TODO: determine revision if not passed
    revision = args.revision

    # TODO: fix: script expects to be run from coreclr repo root
    coreclrDir = os.path.abspath(".")

    # platform = "Linux"
    # platform = "Windows_NT"
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
    
    current_commit = subprocess.check_output(["git", "rev-parse", revision]).decode('utf-8').strip()
    print("diff commit: " + current_commit)
    base_commit = subprocess.check_output(["git", "rev-parse", "master"]).decode('utf-8').strip()
    base_commit = subprocess.check_output(["git", "rev-parse", revision + "^"]).decode('utf-8').strip()
    print("base commit: " + base_commit)
    # test joe's pr: https://ci.dot.net/job/dotnet_coreclr/job/master/job/checked_ubuntu_prtest/9654/
    # https://ci.dot.net/job/dotnet_coreclr/job/master/job/checked_ubuntu/9603/

    localJobDir = os.path.join(jitdiffDir, "artifacts")
    if not os.path.isdir(localJobDir):
        os.makedirs(localJobDir)
    
    baseBinDir = obtain_product_build(cijobs, base_commit, localJobDir, jenkinsJobName, platform, arch, config)


    currentBinDir = obtain_product_build(cijobs, current_commit, localJobDir, jenkinsJobName, platform, arch, config)

    currentCoreclrDir = os.path.join(localJobDir, current_commit)
    
    windowsTestBinDir = obtain_windows_test_build(cijobs, currentCoreclrDir, current_commit, platform, arch, config)
    testBinDir = windowsTestBinDir

    if isUnix(platform):
        unixTestBinDir = obtain_unix_test_build(cijobs, currentCoreclrDir, current_commit, localJobDir, jenkinsJobNamePR, platform, arch, config)
        corefxBinDir = obtain_corefx_build(cijobs, currentCoreclrDir, jenkinsJobName = "ubuntu14.04_release")
        overlayDir = generate_overlay(coreclrDir, currentBinDir, windowsTestBinDir, unixTestBinDir, corefxBinDir)
        coreRootDir = overlayDir
    else:
        coreRootDir = os.path.join(testBinDir, "Tests", "Core_Root")

    ret = runJitdiff(jitdiff, jitdasm, currentBinDir, baseBinDir, coreRootDir, testBinDir, jitdiffDir, platform)

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
