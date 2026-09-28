-- CreateTable
CREATE TABLE `LearningState` (
    `id` VARCHAR(191) NOT NULL,
    `userId` VARCHAR(191) NOT NULL,
    `topic` VARCHAR(191) NOT NULL,
    `currentSection` VARCHAR(191) NULL,
    `goal` TEXT NULL,
    `conceptsCovered` JSON NOT NULL,
    `conceptsUnderstood` JSON NOT NULL,
    `conceptsNotUnderstood` JSON NOT NULL,
    `misconceptions` JSON NOT NULL,
    `currentLevel` VARCHAR(191) NULL,
    `learningStage` VARCHAR(191) NULL,
    `lastQuestion` TEXT NULL,
    `lastProblem` TEXT NULL,
    `nextStep` TEXT NULL,
    `progress` TEXT NULL,
    `isActive` BOOLEAN NOT NULL DEFAULT true,
    `createdAt` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    `updatedAt` DATETIME(3) NOT NULL,

    INDEX `LearningState_userId_isActive_idx`(`userId`, `isActive`),
    UNIQUE INDEX `LearningState_userId_topic_key`(`userId`, `topic`),
    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- AddForeignKey
ALTER TABLE `LearningState` ADD CONSTRAINT `LearningState_userId_fkey` FOREIGN KEY (`userId`) REFERENCES `User`(`id`) ON DELETE CASCADE ON UPDATE CASCADE;
