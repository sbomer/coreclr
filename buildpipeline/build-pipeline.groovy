@Library('dotnet-ci') _


// TODO: simple jit-diff job
// one job for commits (baseline)
// another for PRs
// how to ensure baseline build without initiating a redundant build?
// maybe just do a redundant baseline build for now?

// job folder/name is a deterministic function of os, arch, config, owner, repo, branch?


// coreclr job:
// os, arch, config, commit, coreclr, owner, branch


simpleNode(params.os, 'latest') {
    stage('checkout sources') {
        checkout scm
    }
    stage('build') {
        // bat '.\\build.cmd'
        if (params.os == "Windows_NT") {
            bat 'print building on windows! > build.txt'
            bat 'mkdir bin'
            bat 'print build file > bin/build.txt'
        } else if (params.os == "Ubuntu") {
            sh 'echo building on ubuntu! > build.txt'
            sh 'mkdir bin'
            sh 'echo build file > bin/build.txt'
        }
        
    }
    stage('archive artifacts') {
        archiveArtifacts artifacts: 'build.txt'
        archiveArtifacts artifacts: 'bin/*'
    }
}
// stage('parallel test') {
//     parallel (
//         "windows test" : {
//             simpleNode('Windows_NT', 'latest') {
//                 bat "print from windows"
//             }
//         },
//         "linux test" : {
//             simpleNode('Ubuntu14.04', 'latest') {
//                 sh "echo from linux"
//             }
//         }
//     )
// }
// 
