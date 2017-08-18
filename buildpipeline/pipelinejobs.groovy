import org.dotnet.ci.pipelines.Pipeline



class CoreclrJob {
    enum Configuration {
        debug, checked, release
    }
    enum Platform {
        debian8_4,
        osx10_12,
        windows_nt,
        freebsd,
        centos7_1,
        opensuse42_1,
        rhel7_2,
        ubuntu16_04,
        ubuntu16_10,
        fedora24,
        tizen        
    }
    enum Architecture {
        x86,
        x64
    }
    class TriggerType {
        
    }

    Platform os
    Architecture arch
    Configuration config
}


// for the generated job definitions:
// call createPipeline with the path to the file
// call trigger functions, passing trigger phrase
// maybe override some options (like the job name...)

// dotnet-ci does the following:
// createPipeline makes a Pipeline with context, baseJobName, pipelinefile
//   adds github scm (project, branch, credentialsid)
//   create standard pipeline job
//     enable concurrent build, quiet period of 5 seconds
//     wrap with timestamps, preBuild cleanup, postBuild cleanup
//   emitScmForNonPR, etc.,
//   newJob.with parameters. params become parameters of the job

// def buildPipeline = Pipeline.createPipeline(this, 'buildpipeline/build-pipeline.groovy')
// buildPipeline.triggerPipelineManually()
// buildPipeline.triggerPipelineOnPush()
// buildPipeline.triggerPipelineOnEveryGithubPR('build pipeline status', ".*test\\W+my\\W+job.*")
// 
// def testPipeline = Pipeline.createPipeline(this, 'buildpipeline/test-pipeline.groovy')
// testPipeline.triggerPipelineManually([os: "Windows_NT"])
// testPipeline.triggerPipelineManually([os: "Ubuntu"])
// 
// def jitdiffPipeline = Pipeline.createPipeline(this, 'buildpipeline/jitdiff-pipeline.groovy')
// jitdiffPipeline.triggerPipelineManually([os: "Windows_NT"])
// jitdiffPipeline.triggerPipelineManually([os: "Ubuntu"])
// 
// 
// 
// [''].each { configuration ->
//     testPipeline.triggerPipelineManually(['Configuration':configuration])
// }
              

class PipelineJobDefinition {
    def pipelineFile
    boolean triggerOnPush = false
    boolean triggerManually = false
    String prStatusMessage = null
    boolean triggerOnEveryPR = false
    String prTriggerPhrase = null
    def parameters
}

class JobGenerator {
    def pipelineFile
    boolean triggerOnPush = true
    boolean triggerManually = true
    boolean triggerOnEveryPR = true
    def getPrStatusMessage
    def getPrTriggerPhrase
    def parameterSets
    PipelineJobDefinition[] build() {
        def keys = parameterSets.keySet() as List
        def valueSets = parameterSets.values().combinations()
        def parametersList = valueSets.collect { values ->
            [keys, values].transpose().collectEntries()
        }
        def jobs = parametersList.collect { params ->
            new PipelineJobDefinition(
                pipelineFile : pipelineFile,
                triggerManually : triggerManually,
                triggerOnPush : triggerOnPush,
                triggerOnEveryPR : triggerOnEveryPR,
                prStatusMessage : getPrStatusMessage(params),
                prTriggerPhrase : getPrTriggerPhrase(params),
                parameters : params
            )
        }
        jobs
    }
}

def generateJobs() {

    def buildJobs = new JobGenerator(
        pipelineFile : "buildpipeline/build-pipeline.groovy",
        parameterSets : [
            arch: ["x86", "x64"],
            os: ["Ubuntu", "Windows_NT", "OSX"],
            config: ["Debug", "Checked", "Release"]
        ],
        getPrStatusMessage : { p -> "${p.os} ${p.arch} ${p.config} build" },
        getPrTriggerPhrase : { p -> "build ${p.os} ${p.arch} ${p.config}" }
    ).build()

    def testJobs = new JobGenerator( 
       pipelineFile : "buildpipeline/test-pipeline.groovy",
        parameterSets : [
            arch: ["x86", "x64"],
            os: ["Ubuntu", "Windows_NT", "OSX"],
            config: ["Debug", "Checked", "Release"]
        ],
        getPrStatusMessage : { p -> "${p.os} ${p.arch} ${p.config} test" },
        getPrTriggerPhrase : { p -> "test ${p.os} ${p.arch} ${p.config}" }
    ).build()

    def jitdiffJobs = new JobGenerator(
        pipelineFile : "buildpipeline/jitdiff-pipeline.groovy",
        parameterSets : [
            arch: ["x64"],
            os: ["Ubuntu", "Windows_NT"],
            config: ["Checked"]
        ],
        getPrStatusMessage : { p -> "${p.os} ${p.arch} ${p.config} jitdiff" },
        getPrTriggerPhrase : { p -> "jitdiff ${p.os} ${p.arch} ${p.config}" }
    ).build()

    def jobList = buildJobs + testJobs + jitdiffJobs
    return jobList
}

def setupJob(PipelineJobDefinition j) {
    def pipelineJob = Pipeline.createPipeline(this, j.pipelineFile)
    if (j.triggerManually) {
        pipelineJob.triggerPipelineManually(j.parameters)
    }
    if (j.triggerOnPush) {
        pipelineJob.triggerPipelineOnPush(j.parameters)
    }
    if (j.prStatusMessage != null) {
        if (j.triggerOnEveryPR && j.prTriggerPhrase != null) {
            pipelineJob.triggerPipelineOnEveryGithubPR(j.prStatusMessage, j.prTriggerPhrase, j.parameters)
        } else if (j.triggerOnEveryPR) {
            pipelineJob.triggerPipelineonEveryGithubPR(j.prStatusMessage, j.parameters)
        } else if (j.prTriggerPhrase != null) {
            pipelineJob.triggerPipelineOnGithubPRComment(j.prStatusMessage, j.prTriggerPgrase, j.parameters)
        }
    }
}

generateJobs().each { j -> setupJob(j) }


def project = GithubProject
def branch = GithubBranchName
print project
print branch
folder('testfolder')
Utilities.addStandardFolderView(this, 'testfolder', project)
