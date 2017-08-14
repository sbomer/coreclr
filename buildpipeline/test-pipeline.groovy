@Library('dotnet-ci') _


// TODO: simple jit-diff job
// one job for commits (baseline)
// another for PRs
// how to ensure baseline build without initiating a redundant build?
// maybe just do a redundant baseline build for now?

// job folder/name is a deterministic function of os, arch, config, owner, repo, branch?


// coreclr job:
// os, arch, config, commit, coreclr, owner, branch


simpleNode('Windows_NT', 'latest') {
    stage('checkout sources') {
        checkout scm
    }
    stage('build') {
        // bat '.\\build.cmd'
        bat 'print building! > build.txt'
    }
    stage('archive artifacts') {
        archiveArtifacts artifacts: 'build.txt'
    }
    stage('parallel test') {
        parallel (
            "windows test" : {
                node('windows') {
                    bat "print from windows"
                }
            },
            "linux test" : {
                node('linux') {
                    sh "echo from linux"
                }
            }
        )
    }
}
