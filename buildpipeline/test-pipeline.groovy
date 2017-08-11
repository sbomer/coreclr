@Library('dotnet-ci') _

simpleNode('Windows_NT', 'latest') {
    stage('checkout sources') {
        checkout scm
    }
    stage('build') {
        bat '.\\build.cmd'
    }
}
