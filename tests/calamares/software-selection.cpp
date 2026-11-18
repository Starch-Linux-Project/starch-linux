// SPDX-License-Identifier: GPL-3.0-or-later
// Run only in the isolated test chroot with software-helper.py substituted.
#include "GlobalStorage.h"
#include "JobQueue.h"
#include "Job.h"
#include "utils/PluginFactory.h"
#include "viewpages/ViewStep.h"
#include <QApplication>
#include <QDialog>
#include <QEventLoop>
#include <QFile>
#include <QPlainTextEdit>
#include <QPluginLoader>
#include <QPushButton>
#include <QThread>
#include <QTimer>
#include <iostream>
#include <stdexcept>

static void check(bool value, const char* message)
{
    if (!value) throw std::runtime_error(message);
}

class FailedEssentialJob : public Calamares::Job
{
public:
    QString prettyName() const override { return "Simulated essential OS failure"; }
    Calamares::JobResult exec() override { return Calamares::JobResult::error("Simulated failure"); }
};

int main(int argc, char** argv)
{
    QApplication app(argc, argv);
    Calamares::JobQueue queue;
    auto* gs = queue.globalStorage();
    QPluginLoader loader("/usr/lib/calamares/modules/starchsoftware/libcalamares_viewmodule_starchsoftware.so");
    auto* factory = qobject_cast<CalamaresPluginFactory*>(loader.instance());
    check(factory, "Could not load software plugin");
    auto* step = factory->create<Calamares::ViewStep>();
    auto* page = step->widget();
    auto* pacman = page->findChild<QPlainTextEdit*>("starchSoftware_pacman");
    auto* flathub = page->findChild<QPlainTextEdit*>("starchSoftware_flathub");
    check(pacman && flathub, "Missing separate input fields");
    check(pacman->toPlainText().isEmpty() && flathub->toPlainText().isEmpty(), "Unexpected presets");
    pacman->setPlainText("foo, foo\nmissing <b>");
    flathub->setPlainText("org.example.App org.example.App");
    page->hide();
    check(step->widget() == page, "Navigation recreated page");
    check(gs->value("starchSoftware_pacman").toString() == "foo, foo\nmissing <b>", "Lost raw entries");
    check(step->prettyStatus().contains("&lt;b&gt;") && !step->prettyStatus().contains("foo, foo"), "Summary escaping/dedup failed");
    delete step;
    step = factory->create<Calamares::ViewStep>();
    page = step->widget();
    pacman = page->findChild<QPlainTextEdit*>("starchSoftware_pacman");
    flathub = page->findChild<QPlainTextEdit*>("starchSoftware_flathub");
    check(pacman->toPlainText() == "foo, foo\nmissing <b>", "Recreation lost entries");

    auto run = [&](bool skip, bool essentialFailure = false) {
        auto job = step->jobs().first();
        bool succeeded = true;
        bool sawLiveOutput = false;
        bool clicked = false;
        bool reviewed = false;
        QEventLoop loop;
        QObject::connect(&queue, &Calamares::JobQueue::finished, &loop, &QEventLoop::quit);
        QObject::connect(&queue, &Calamares::JobQueue::failed, &loop, [&] { succeeded = false; });
        QTimer poll;
        QObject::connect(&poll, &QTimer::timeout, [&] {
            auto* dialog = qobject_cast<QDialog*>(QApplication::activeModalWidget());
            if (!dialog) return;
            auto* live = dialog->findChild<QPlainTextEdit*>("starchSoftwareOutput");
            if (live && live->toPlainText().contains("downloading foo")) sawLiveOutput = true;
            for (auto* button : dialog->findChildren<QPushButton*>()) {
                if (skip && !clicked && button->text().startsWith("Skip remaining") && button->isEnabled()) {
                    // Wait until the fake transaction has actually started.
                    QFile log("/tmp/starch-software-test.log");
                    if (log.open(QIODevice::ReadOnly) && log.readAll().contains("start foo")) {
                        button->click();
                        clicked = true;
                        dialog->reject(); // Escape/close cannot interrupt the transaction.
                    }
                }
                if (button->text() == "Continue" && button->isEnabled()) { reviewed = true; button->click(); }
            }
        });
        poll.start(5);
        QTimer::singleShot(10000, &loop, [] { qFatal("Software test timed out"); });
        if (essentialFailure) queue.enqueue(1, {Calamares::job_ptr(new FailedEssentialJob)});
        queue.enqueue(1, {job});
        queue.start();
        loop.exec();
        if (!essentialFailure && !pacman->toPlainText().isEmpty()) check(sawLiveOutput, "No live package output was displayed");
        check(succeeded != essentialFailure, "Incorrect OS job failure status");
        if (!essentialFailure && !pacman->toPlainText().isEmpty()) check(reviewed, "Results closed before review");
        if (skip) check(clicked, "Skip was not exercised");
        return gs->value("starchSoftwareResults").toString();
    };
    pacman->clear();
    flathub->clear();
    QFile::remove("/tmp/starch-software-test.log");
    run(false);
    check(!QFile::exists("/tmp/starch-software-test.log"), "Empty selection launched helper");
    pacman->setPlainText("foo");
    check(run(false).contains("Installed: foo"), "Successful request not reported");
    pacman->setPlainText("foo foo, missing bar");
    flathub->setPlainText("org.example.App org.example.App");
    auto result = run(false);
    check(result.count("Installed: foo") == 1, "Duplicate package installed twice");
    check(result.contains("Warning: failed to install missing") && result.contains("Installed: bar")
          && result.count("Installed: org.example.App") == 1, "Warning did not continue remaining installs");
    QFile::remove("/tmp/starch-software-test.log");
    pacman->setPlainText("foo bar");
    result = run(true);
    QFile log("/tmp/starch-software-test.log");
    check(log.open(QIODevice::ReadOnly), "Missing transaction log");
    const auto transaction = log.readAll();
    check(transaction == "start foo\nend foo\n", "Skip killed current transaction or started another");
    check(result.contains("Skipped: bar") && result.contains("Skipped: org.example.App"), "Skipped requests not reported");
    log.close();
    QFile::remove("/tmp/starch-software-test.log");
    run(false, true);
    check(!QFile::exists("/tmp/starch-software-test.log"), "Optional helper ran after essential OS failure");
    delete step;
    std::cout << "Additional Software navigation, deduplication, warnings and safe skip passed.\n";
}
