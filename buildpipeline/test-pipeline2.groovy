@Library('dotnet-ci') _

simpleNode('Windows_NT', 'latest') {
    stage('obtain artifacts') {
        
    }
    stage('run other job') {
        build job: 'test-pipeline'
    }
    stage('obtain artifacts') {
               
    }
}
